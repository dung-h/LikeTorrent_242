import hashlib
import json
import sys
import os
from config import PIECE_SIZE

class Metainfo:
    def __init__(self, filename, tracker_url):
        self.filename = filename
        self.tracker_url = tracker_url
        if isinstance(filename, list):
            meta = Metainfo.create_torrent_for_files(filename, piece_length=PIECE_SIZE)
            self.files = meta["files"]
            self.piece_length = meta["piece_length"]
            self.pieces = [p for p in meta["pieces"]]
            self.torrent_hash = meta["torrent_hash"]
        else:
            file_size = self.get_file_size(filename)
            self.files = [{
                "path": os.path.basename(filename),
                "length": file_size,
                "start_offset": 0
            }]
            # Fix: use file_size if it's smaller than PIECE_SIZE
            if file_size < PIECE_SIZE:
                self.piece_length = file_size
            else:
                self.piece_length = PIECE_SIZE
            self.pieces = self.split_into_pieces()
            self.torrent_hash = self.generate_hash()
        self.magnet_text = f"magnet:?xt=urn:btih:{self.torrent_hash}&tr={tracker_url}"
    @staticmethod
    def create_torrent_for_files(file_paths, piece_length=PIECE_SIZE, name="MultiFileTorrent"):
        """Create a torrent for multiple files with proper offset tracking."""
        files_list = []
        pieces = b""
        file_start_offset = 0  # Track the absolute offset of each file

        for filepath in file_paths:
            file_size = os.path.getsize(filepath)
            rel_path = os.path.basename(filepath)  # Use relative path if needed

            # Add file with its starting offset
            files_list.append({
                "path": rel_path,
                "length": file_size,
                "start_offset": file_start_offset
            })
            file_start_offset += file_size

            # Generate pieces as before
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(piece_length)
                    if not chunk:
                        break
                    pieces += hashlib.sha1(chunk).digest()

        metainfo = {
            "name": name,
            "piece_length": piece_length,
            "pieces": [pieces[i:i+20].hex() for i in range(0, len(pieces), 20)],  # assuming SHA-1 (20 bytes)
            "files": files_list,
            "torrent_hash": hashlib.sha1(pieces).hexdigest()
        }
        return metainfo

    def get_file_size(self, filename):
        with open(filename, "rb") as f:
            return os.path.getsize(filename)

    def split_into_pieces(self):
        pieces = []
        with open(self.filename, "rb") as f:
            while True:
                piece = f.read(PIECE_SIZE)
                if not piece:
                    break
                pieces.append(hashlib.sha1(piece).hexdigest())
        return pieces

    def __getitem__(self, key):
        # Allows dictionary-style access: metainfo["pieces"]
        if key == "tracker":
            return self.tracker_url
        return getattr(self, key)

    @staticmethod
    def load(torrent_file):
        with open(torrent_file, "r") as f:
            meta_dict = json.load(f)
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
        print("Usage: python metainfo.py <input_file or files comma-separated> <tracker_url> <output_torrent_file>")
        sys.exit(1)

    input_param = sys.argv[1]
    tracker_url = sys.argv[2]
    output_file = sys.argv[3]

    # If multiple files are provided separated by commas, use create_torrent_for_files
    if "," in input_param:
        file_paths = input_param.split(",")
        meta_dict = Metainfo.create_torrent_for_files(file_paths)
        with open(output_file, "w") as f:
            json.dump(meta_dict, f)
        print(f"Multi-file torrent saved as {output_file}")
    else:
        if not os.path.exists(input_param):
            print(f"Error: File '{input_param}' does not exist.")
            sys.exit(1)
        meta = Metainfo(input_param, tracker_url)
        meta.save(output_file)

if __name__ == "__main__":
    main()