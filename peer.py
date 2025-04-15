# File: peer.py
import socket
import time
import hashlib
import json

class Peer:
    def __init__(self, peer_id, ip, port, piece_manager):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.piece_manager = piece_manager
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            print(f"Attempting to connect to peer {self.peer_id} at {self.ip}:{self.port}")
            self.sock.connect((self.ip, self.port))
            self.sock.send("ESTABLISH".encode())
            response = self.sock.recv(1024).decode().strip()
            if response == "ESTABLISHED":
                print(f"Successfully connected to {self.peer_id}")
                return True
            else:
                print(f"Failed to establish connection with {self.peer_id}: {response}")
                return False
        except Exception as e:
            print(f"Connection error with {self.peer_id}: {e}")
            return False

    def download_piece(self, piece_index, my_peer_id):
        try:
            request = f"REQUEST:{piece_index}"
            print(f"Sending request: {request} to {self.peer_id}")
            self.sock.send(request.encode())
            
            expected_size = self.piece_manager.expected_piece_length(piece_index)
            data = b""
            while len(data) < expected_size:
                chunk = self.sock.recv(4096)
                if not chunk:
                    print(f"Connection closed by {self.peer_id} while downloading piece {piece_index}")
                    return False
                data += chunk
                print(f"Received {len(chunk)} bytes, total: {len(data)}/{expected_size}")
            
            if len(data) > expected_size:
                data = data[:expected_size]
            
            return self.piece_manager.piece_complete(piece_index, data)
        except Exception as e:
            print(f"Download error: {e}")
            return False

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None