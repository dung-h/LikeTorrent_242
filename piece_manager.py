# File: piece_manager.py
import os
from config import PIECE_SIZE, DOWNLOAD_DIR

class PieceManager:
    def __init__(self, metainfo, is_seeder=False):
        self.metainfo = metainfo
        self.total_pieces = len(metainfo["pieces"])
        self.have_pieces = [False] * self.total_pieces
        self.files = metainfo["files"]
        self.download_dir = DOWNLOAD_DIR
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self.output_file = os.path.join(DOWNLOAD_DIR, self.files[0]["path"])
        
        # Only create empty file for downloaders, not seeders
        if not is_seeder:
            # Initialize empty file
            with open(self.output_file, "wb") as f:
                f.truncate(self.files[0]["length"])

    def piece_complete(self, piece_index, piece_data):
        if not self.have_pieces[piece_index]:
            self.have_pieces[piece_index] = True
            self.write_piece(piece_index, piece_data)

    def write_piece(self, piece_index, piece_data):
        offset = piece_index * PIECE_SIZE
        with open(self.output_file, "r+b") as f:
            f.seek(offset)
            f.write(piece_data)

    def all_pieces_downloaded(self):
        return all(self.have_pieces)

    def missing_pieces(self):
        return [i for i, have in enumerate(self.have_pieces) if not have]