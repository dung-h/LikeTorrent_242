# File: piece_manager.py
import os
import json
import sqlite3
from config import PIECE_SIZE, DOWNLOAD_DIR

class PieceManager:
    def __init__(self, metainfo, is_seeder=False, db=None):
        self.db = db
        self.metainfo = metainfo
        self.total_pieces = len(metainfo["pieces"])
        self.download_dir = metainfo.get("download_dir", DOWNLOAD_DIR)
        os.makedirs(self.download_dir, exist_ok=True)
        self.files = metainfo["files"]

        # Load or initialize piece ownership
        c = self.db.cursor()
        c.execute('SELECT pieces_owned FROM peer_torrents WHERE torrent_hash = ?', (metainfo["torrent_hash"],))
        result = c.fetchone()
        self.have_pieces = json.loads(result[0]) if result else ([True] * self.total_pieces if is_seeder else [False] * self.total_pieces)

        if not is_seeder:
            for file_info in self.files:
                path = os.path.join(self.download_dir, file_info["path"])
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.truncate(file_info["length"])

    def piece_complete(self, piece_index, piece_data):
        if not self.have_pieces[piece_index]:
            self.have_pieces[piece_index] = True
            self.write_piece(piece_index, piece_data)
            c = self.db.cursor()
            c.execute('UPDATE peer_torrents SET pieces_owned = ?, downloaded_bytes = ? WHERE torrent_hash = ?',
                      (json.dumps(self.have_pieces),
                       sum(self.have_pieces) * self.metainfo["piece_length"],
                       self.metainfo["torrent_hash"]))
            self.db.commit()

    def write_piece(self, piece_index, piece_data):
        offset = piece_index * self.metainfo["piece_length"]
        remaining = len(piece_data)
        for file_info in self.files:
            file_path = os.path.join(self.download_dir, file_info["path"])
            file_start = file_info.get("start_offset", 0)
            file_length = file_info["length"]
            if offset >= file_start + file_length:
                continue
            if offset + remaining <= file_start:
                break
            start_in_file = max(0, offset - file_start)
            bytes_to_write = min(remaining, file_length - start_in_file)
            with open(file_path, "r+b") as f:
                f.seek(start_in_file)
                f.write(piece_data[:bytes_to_write])
            piece_data = piece_data[bytes_to_write:]
            remaining -= bytes_to_write
            if remaining <= 0:
                break

    def all_pieces_downloaded(self):
        return all(self.have_pieces)

    def missing_pieces(self):
        return [i for i, have in enumerate(self.have_pieces) if not have]