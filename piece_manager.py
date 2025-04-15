# File: piece_manager.py
import hashlib
import json
import math
import os
import sqlite3
import threading
from config import DOWNLOAD_DIR, PIECE_SIZE

class PieceManager:
    def __init__(self, metainfo, peer_id):
        self.metainfo = metainfo
        self.download_dir = DOWNLOAD_DIR
        self.peer_id = peer_id
        self.files = metainfo["files"]
        self.total_pieces = len(metainfo["pieces"])
        self.piece_length = metainfo["piece_length"]
        self.file_lock = threading.Lock()
        self.init_db()
        self.have_pieces = self.load_pieces()
        # Initialize files with correct sizes
        for file_info in self.files:
            file_path = os.path.join(self.download_dir, file_info["path"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            if not os.path.exists(file_path) or os.path.getsize(file_path) != file_info["length"]:
                with open(file_path, "wb") as f:
                    f.truncate(file_info["length"])
                print(f"Initialized file {file_path} to {file_info['length']} bytes")

    def get_db_connection(self):
        """Create a new database connection."""
        return sqlite3.connect('torrent.db', timeout=10)

    def init_db(self):
        """Initialize required database tables."""
        conn = self.get_db_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS peer_torrents (
                        peer_id TEXT,
                        torrent_hash TEXT,
                        pieces_owned TEXT,
                        downloaded_bytes INTEGER,
                        state TEXT,
                        PRIMARY KEY (peer_id, torrent_hash)
                     )''')
        conn.commit()
        conn.close()
        print("Initialized peer_torrents table")

    def load_pieces(self):
        """Load piece status from database or verify file contents."""
        conn = self.get_db_connection()
        c = conn.cursor()
        c.execute('SELECT pieces_owned FROM peer_torrents WHERE peer_id = ? AND torrent_hash = ?',
                  (self.peer_id, self.metainfo["torrent_hash"]))
        result = c.fetchone()
        pieces = [False] * self.total_pieces

        # Try loading from database
        if result:
            try:
                pieces = json.loads(result[0])
                if len(pieces) != self.total_pieces:
                    print(f"Piece count mismatch: expected {self.total_pieces}, got {len(pieces)}")
                    pieces = [False] * self.total_pieces
            except json.JSONDecodeError:
                print("Invalid pieces_owned JSON, resetting pieces")
                pieces = [False] * self.total_pieces

        # Verify file existence and sizes
        all_files_exist = True
        for file_info in self.files:
            path = os.path.join(self.download_dir, file_info["path"])
            if not os.path.exists(path) or os.path.getsize(path) != file_info["length"]:
                print(f"File missing or incorrect size: {path}")
                all_files_exist = False
                break

        # If files exist, validate pieces by hashing
        if all_files_exist:
            verified_pieces = [False] * self.total_pieces
            for piece_index in range(self.total_pieces):
                piece_data = bytearray()
                offset = piece_index * self.piece_length
                bytes_read = 0
                expected_length = self.expected_piece_length(piece_index)

                for file_info in self.files:
                    file_path = os.path.join(self.download_dir, file_info["path"])
                    file_offset = max(0, offset - bytes_read)
                    bytes_to_read = min(file_info["length"] - file_offset, expected_length - len(piece_data))

                    if bytes_to_read <= 0:
                        continue

                    with open(file_path, "rb") as f:
                        f.seek(file_offset)
                        data = f.read(bytes_to_read)
                        piece_data.extend(data)
                        bytes_read += len(data)

                piece_hash = hashlib.sha1(piece_data).hexdigest()
                expected_hash = self.metainfo["pieces"][piece_index]
                if piece_hash == expected_hash:
                    verified_pieces[piece_index] = True
                else:
                    print(f"Piece {piece_index} hash mismatch: got {piece_hash}, expected {expected_hash}")

            # Use verified pieces if database is incomplete
            if any(verified_pieces):
                pieces = verified_pieces
                print(f"Loaded {pieces.count(True)} pieces from file verification")
            elif pieces.count(True) > verified_pieces.count(True):
                print("Using database pieces as they indicate more progress")
            else:
                pieces = verified_pieces

        # Update database with current state
        c.execute('''INSERT OR REPLACE INTO peer_torrents (peer_id, torrent_hash, pieces_owned, downloaded_bytes, state)
                     VALUES (?, ?, ?, ?, ?)''',
                  (self.peer_id, self.metainfo["torrent_hash"], json.dumps(pieces),
                   sum(pieces) * self.piece_length, 'downloading'))
        conn.commit()
        conn.close()
        print(f"Loaded pieces: {pieces.count(True)}/{self.total_pieces} marked as complete")
        return pieces

    def expected_piece_length(self, piece_index):
        """Calculate the expected length of a piece."""
        total_file_length = sum(file_info["length"] for file_info in self.files)
        piece_length = self.metainfo["piece_length"]
        if (piece_index + 1) * piece_length > total_file_length:
            return total_file_length - piece_index * piece_length
        return piece_length

    def piece_complete(self, piece_index, data):
        """Write a piece to disk and mark it complete if valid."""
        piece_hash = hashlib.sha1(data).hexdigest()
        expected_hash = self.metainfo["pieces"][piece_index]
        print(f"Piece {piece_index}: Hash {piece_hash}, Expected {expected_hash}")
        if piece_hash != expected_hash:
            print(f"Piece {piece_index} hash mismatch")
            return False

        expected_length = self.expected_piece_length(piece_index)
        if len(data) != expected_length:
            print(f"Piece {piece_index} length mismatch: got {len(data)}, expected {expected_length}")
            return False

        with self.file_lock:
            offset = piece_index * self.piece_length
            bytes_written = 0
            for file_info in self.files:
                file_path = os.path.join(self.download_dir, file_info["path"])
                file_offset = max(0, offset - bytes_written)
                bytes_to_write = min(file_info["length"] - file_offset, len(data) - bytes_written)

                if bytes_to_write <= 0:
                    continue

                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "r+b" if os.path.exists(file_path) else "wb") as f:
                    f.seek(file_offset)
                    f.write(data[bytes_written:bytes_written + bytes_to_write])
                    f.truncate(file_info["length"])

                bytes_written += bytes_to_write

            if bytes_written != len(data):
                print(f"Piece {piece_index} write error: wrote {bytes_written}, expected {len(data)}")
                return False

        self.have_pieces[piece_index] = True
        conn = self.get_db_connection()
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO peer_torrents (peer_id, torrent_hash, pieces_owned, downloaded_bytes, state)
                     VALUES (?, ?, ?, ?, ?)''',
                  (self.peer_id, self.metainfo["torrent_hash"], json.dumps(self.have_pieces),
                   sum(self.have_pieces) * self.piece_length, 'downloading'))
        conn.commit()
        conn.close()
        print(f"Piece {piece_index} written and marked complete")
        return True

    def missing_pieces(self):
        """Return indices of missing pieces."""
        return [i for i, have in enumerate(self.have_pieces) if not have]

    def all_pieces_downloaded(self):
        """Check if all pieces are downloaded."""
        return all(self.have_pieces)