# File: piece_manager.py
import os
import math
import hashlib
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PieceManager:
    def __init__(self, metainfo, peer_id, base_path):
        self.metainfo = metainfo
        self.peer_id = peer_id
        self.base_path = base_path
        self.total_pieces = math.ceil(sum(f["length"] for f in metainfo["files"]) / metainfo["piece_length"])
        self.have_pieces = [False] * self.total_pieces
        self.files = self._map_files()
        self._check_existing_files()
        logging.info(f"Initialized PieceManager: {self.total_pieces} pieces, base_path={base_path}")

    def _map_files(self):
        files = []
        offset = 0
        for file_info in self.metainfo["files"]:
            file_path = os.path.normpath(os.path.join(self.base_path, file_info["path"]))
            files.append({
                "path": file_path,
                "length": file_info["length"],
                "offset": offset
            })
            offset += file_info["length"]
        return files

    def _check_existing_files(self):
        all_complete = True
        for piece_index in range(self.total_pieces):
            piece_data = self._read_piece(piece_index)
            if piece_data is None:
                all_complete = False
                continue
            expected_hash = self.metainfo["pieces"][piece_index]
            piece_hash = hashlib.sha1(piece_data).hexdigest()
            self.have_pieces[piece_index] = (piece_hash == expected_hash)
            if not self.have_pieces[piece_index]:
                all_complete = False
                logging.info(f"Piece {piece_index} hash mismatch: expected {expected_hash}, got {piece_hash}")
        if all_complete:
            logging.info("All pieces verified, ready to seed")
        else:
            logging.info(f"Missing or invalid pieces: {self.have_pieces.count(False)}")

    def _read_piece(self, piece_index):
        piece_offset = piece_index * self.metainfo["piece_length"]
        piece_length = self.expected_piece_length(piece_index)
        piece_data = bytearray(piece_length)
        bytes_read = 0

        for file_info in self.files:
            file_start = file_info["offset"]
            file_end = file_start + file_info["length"]
            if piece_offset + piece_length <= file_start or piece_offset >= file_end:
                continue
            start_in_file = max(0, piece_offset - file_start)
            bytes_to_read = min(
                file_info["length"] - start_in_file,
                piece_length - bytes_read
            )
            try:
                with open(file_info["path"], "rb") as f:
                    f.seek(start_in_file)
                    data = f.read(bytes_to_read)
                    piece_data[bytes_read:bytes_read + len(data)] = data
                    bytes_read += len(data)
            except Exception as e:
                logging.error(f"Failed to read {file_info['path']}: {e}")
                return None
        return piece_data if bytes_read == piece_length else None

    def write_piece(self, piece_index, piece_data):
        piece_offset = piece_index * self.metainfo["piece_length"]
        bytes_written = 0
        for file_info in self.files:
            file_start = file_info["offset"]
            file_end = file_start + file_info["length"]
            if piece_offset + len(piece_data) <= file_start or piece_offset >= file_end:
                continue
            start_in_file = max(0, piece_offset - file_start)
            bytes_to_write = min(
                file_info["length"] - start_in_file,
                len(piece_data) - bytes_written
            )
            os.makedirs(os.path.dirname(file_info["path"]), exist_ok=True)
            try:
                with open(file_info["path"], "r+b" if os.path.exists(file_info["path"]) else "wb") as f:
                    f.seek(start_in_file)
                    f.write(piece_data[bytes_written:bytes_written + bytes_to_write])
                    bytes_written += bytes_to_write
            except Exception as e:
                logging.error(f"Failed to write {file_info['path']}: {e}")
                return False
        if bytes_written == len(piece_data):
            self.have_pieces[piece_index] = True
            logging.info(f"Wrote piece {piece_index}")
            return True
        return False

    def piece_complete(self, piece_index, piece_data):
        expected_hash = self.metainfo["pieces"][piece_index]
        piece_hash = hashlib.sha1(piece_data).hexdigest()
        if piece_hash != expected_hash:
            logging.warning(f"Piece {piece_index} hash mismatch: expected {expected_hash}, got {piece_hash}")
            return False
        return self.write_piece(piece_index, piece_data)

    def expected_piece_length(self, piece_index):
        total_length = sum(f["length"] for f in self.metainfo["files"])
        regular_piece_length = self.metainfo["piece_length"]
        if piece_index == self.total_pieces - 1:
            return total_length - (piece_index * regular_piece_length)
        return regular_piece_length

    def all_pieces_downloaded(self):
        return all(self.have_pieces)

    def missing_pieces(self):
        return [i for i, have in enumerate(self.have_pieces) if not have]