# File: peer.py
import socket
from config import PIECE_SIZE
import time
import hashlib

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
            print(f"Attempting to connect to peer {self.peer_id} at {self.ip}:{self.port}")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.ip, self.port))
            
            connecting_peer_id = self.piece_manager.client_peer_id if hasattr(self.piece_manager, 'client_peer_id') else "unknown_peer"
            message = f"ESTABLISH:{connecting_peer_id}"
            print(f"Sending: {message}")
            self.sock.send(message.encode())
            
            response = self.sock.recv(1024).decode()
            print(f"Received response: {response}")
            
            if response == "ESTABLISHED":
                print(f"Successfully connected to {self.peer_id}")
                missing = self.piece_manager.missing_pieces()
                print(f"Missing pieces to download: {missing}")
                return True
            else:
                print(f"Failed to establish connection: unexpected response")
                self.sock.close()
                return False
        except Exception as e:
            print(f"Connection error: {e}")
            if hasattr(self, 'sock') and self.sock:
                self.sock.close()
            return False

    def download_piece(self, piece_index, local_peer_id):
        try:
            message = f"REQUEST:{piece_index}"
            expected_size = self.piece_manager.expected_piece_length(piece_index)
            print(f"Requesting piece {piece_index} (expected size: {expected_size} bytes)")
            self.sock.send(message.encode())
            
            piece_data = b""
            while len(piece_data) < expected_size:
                try:
                    chunk = self.sock.recv(min(4096, expected_size - len(piece_data)))
                    if not chunk:  # Connection closed
                        if len(piece_data) == expected_size:
                            print(f"Received all {len(piece_data)} bytes, connection closed normally")
                            break
                        else:
                            print(f"Connection closed prematurely, received {len(piece_data)}/{expected_size} bytes")
                            return False
                    piece_data += chunk
                    print(f"Received {len(piece_data)}/{expected_size} bytes")
                except socket.timeout:
                    print(f"Timeout waiting for data, received {len(piece_data)}/{expected_size} bytes")
                    return False
            
            # Verify the piece
            received_hash = hashlib.sha1(piece_data).hexdigest()
            expected_hash = self.piece_manager.metainfo["pieces"][piece_index]
            print(f"Receiver calculated hash: {received_hash}")
            print(f"Expected hash from torrent: {expected_hash}")
            
            if len(piece_data) > 0:
                print(f"Piece {piece_index}: Verifying and writing {len(piece_data)} bytes")
                if self.piece_manager.piece_complete(piece_index, piece_data):
                    print(f"✓ Piece {piece_index} successfully verified and written")
                    return True
                else:
                    print(f"✗ Piece {piece_index} verification failed")
                    return False
            return False
        except Exception as e:
            print(f"Download error: {e}")
            return False

    def close(self):
        if self.sock:
            self.sock.close()