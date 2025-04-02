# File: peer.py
import socket
from config import PIECE_SIZE

class Peer:
    def __init__(self, peer_id, ip, port, piece_manager):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.piece_manager = piece_manager
        self.sock = None

    # Recommended improvements for peer.py - connect and download_piece methods

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)  # Set timeout
            print(f"Connecting to peer {self.peer_id} at {self.ip}:{self.port}")
            self.sock.connect((self.ip, self.port))
            self.sock.send(f"ESTABLISH:{self.peer_id}".encode())
            response = self.sock.recv(1024).decode()
            if "ESTABLISHED" in response:
                print(f"Connected to peer {self.peer_id}")
                return True
            return False
        except Exception as e:
            print(f"Error connecting to peer {self.peer_id}: {e}")
            if self.sock:
                self.sock.close()
                self.sock = None
            return False

    def download_piece(self, piece_index):
        if not self.sock:
            if not self.connect():
                print(f"Failed to reconnect to peer {self.peer_id}")
                return
                
        try:
            print(f"Requesting piece {piece_index} from peer {self.peer_id}")
            self.sock.send(f"REQUEST:{piece_index}".encode())
            piece_data = b""
            total_received = 0
            expected_size = self.piece_manager.metainfo["piece_length"]
            
            # Set a longer timeout for receiving large pieces
            self.sock.settimeout(30)
            
            while total_received < expected_size:
                try:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        # Connection closed prematurely
                        break
                    piece_data += chunk
                    total_received += len(chunk)
                except socket.timeout:
                    print(f"Timeout receiving from peer {self.peer_id}")
                    break
                
            if len(piece_data) > 0:
                self.piece_manager.write_piece(piece_index, piece_data)
                print(f"Downloaded piece {piece_index} from peer {self.peer_id}. Size: {len(piece_data)}")
                return True
            else:
                print(f"Empty piece data received from peer {self.peer_id}")
                return False
        except Exception as e:
            print(f"Error downloading piece {piece_index}: {e}")
            return False
        
    def close(self):
        if self.sock:
            self.sock.close()