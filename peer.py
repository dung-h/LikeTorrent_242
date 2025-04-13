# File: peer.py
import socket
from config import PIECE_SIZE
import time

class Peer:
    def __init__(self, peer_id, ip, port, piece_manager, db):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.piece_manager = piece_manager
        self.db = db
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.ip, self.port))
            self.sock.send(f"ESTABLISH:{self.peer_id}".encode())
            response = self.sock.recv(1024).decode()
            return "ESTABLISHED" in response
        except Exception as e:
            print(f"Connect error: {e}")
            if self.sock:
                self.sock.close()
            return False

    def download_piece(self, piece_index, client_peer_id):
        try:
            self.sock.settimeout(30)
            self.sock.send(f"REQUEST:{piece_index}".encode())
            piece_data = bytearray()
            total_received = 0
            expected_size = self.piece_manager.metainfo["piece_length"]
            while total_received < expected_size:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                piece_data.extend(chunk)
                total_received += len(chunk)
            if total_received > 0:
                self.piece_manager.piece_complete(piece_index, bytes(piece_data))
                c = self.db.cursor()
                c.execute('''INSERT INTO peer_interactions (source_peer_id, target_peer_id, torrent_hash, piece_index, bytes_transferred)
                             VALUES (?, ?, ?, ?, ?)''',
                          (self.peer_id, client_peer_id, self.piece_manager.metainfo["torrent_hash"], piece_index, total_received))
                self.db.commit()
                return True
            return False
        except Exception as e:
            print(f"Download error: {e}")
            return False

    def close(self):
        if self.sock:
            self.sock.close()