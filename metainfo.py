# File: metainfo.py
import hashlib
import json
import sys
import os
from config import PIECE_SIZE

class Metainfo:
    def __init__(self, filename, tracker_url):
        self.filename = filename
        self.tracker_url = tracker_url
        self.files = [{"path": os.path.basename(filename), "length": self.get_file_size(filename)}]
        self.piece_length = PIECE_SIZE
        self.pieces = self.split_into_pieces()
        self.torrent_hash = self.generate_hash()

    def get_file_size(self, filename):
        with open(filename, "rb") as f:
            return os.path.getsize(filename)  # More efficient than reading the whole file

    def split_into_pieces(self):
        pieces = []
        with open(self.filename, "rb") as f:
            while True:
                piece = f.read(PIECE_SIZE)
                if not piece:
                    break
                pieces.append(hashlib.sha1(piece).hexdigest())
        return pieces
    # Add this method to the Metainfo class, just after the save method
    # In metainfo.py, modify the __getitem__ method
    def __getitem__(self, key):
        # This allows dictionary-style access: metainfo["pieces"]
        if key == "tracker":
            return self.tracker_url
        return getattr(self, key)
    
    @staticmethod
    def load(torrent_file):
        with open(torrent_file, "r") as f:
            meta_dict = json.load(f)
        
        # Create a new instance without calling __init__
        meta = Metainfo.__new__(Metainfo)
        meta.tracker_url = meta_dict["tracker"]
        meta.files = meta_dict["files"]
        meta.piece_length = meta_dict["piece_length"]
        meta.pieces = meta_dict["pieces"]
        meta.torrent_hash = meta_dict["torrent_hash"]
        meta.filename = meta_dict["files"][0]["path"]
        return meta

    def generate_hash(self):
        data = {"tracker": self.tracker_url, "files": self.files, "piece_length": self.piece_length}
        return hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def to_dict(self):
        return {
            "tracker": self.tracker_url,
            "files": self.files,
            "piece_length": self.piece_length,
            "pieces": self.pieces,
            "torrent_hash": self.torrent_hash
        }

    def save(self, torrent_file):
        with open(torrent_file, "w") as f:
            json.dump(self.to_dict(), f)
        print(f"Torrent file saved as {torrent_file}")

def main():
    if len(sys.argv) != 4:
        print("Usage: python metainfo.py <input_file> <tracker_url> <output_torrent_file>")
        print("Example: python metainfo.py sample.txt http://localhost:8000 sample.torrent")
        sys.exit(1)

    input_file = sys.argv[1]
    tracker_url = sys.argv[2]
    output_file = sys.argv[3]

    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' does not exist.")
        sys.exit(1)

    # Create and save the torrent file
    meta = Metainfo(input_file, tracker_url)
    meta.save(output_file)

if __name__ == "__main__":
    main()