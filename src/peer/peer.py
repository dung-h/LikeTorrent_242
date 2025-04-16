# File: peer.py
import socket
import time
import hashlib
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
            self.sock.settimeout(15)
            logging.info(f"Attempting to connect to peer {self.peer_id} at {self.ip}:{self.port}")
            self.sock.connect((self.ip, self.port))
            self.sock.send("ESTABLISH".encode())
            response = self.sock.recv(1024).decode().strip()
            if response == "ESTABLISHED":
                logging.info(f"Successfully connected to {self.peer_id}")
                return True
            else:
                logging.warning(f"Failed to establish connection with {self.peer_id}: {response}")
                return False
        except Exception as e:
            logging.error(f"Connection error with {self.peer_id}: {e}")
            return False

    def download_piece(self, piece_index, my_peer_id):
        try:
            request = f"REQUEST:{piece_index}"
            logging.info(f"Sending request: {request} to {self.peer_id}")
            self.sock.send(request.encode())
            
            expected_size = self.piece_manager.expected_piece_length(piece_index)
            data = b""
            while len(data) < expected_size:
                chunk = self.sock.recv(4096)
                if not chunk:
                    logging.error(f"Connection closed by {self.peer_id} while downloading piece {piece_index}")
                    return False
                data += chunk
                logging.debug(f"Received {len(chunk)} bytes, total: {len(data)}/{expected_size}")
            
            if len(data) != expected_size:
                logging.error(f"Piece {piece_index} size mismatch: expected {expected_size}, got {len(data)}")
                return False
            
            logging.info(f"Downloaded piece {piece_index} with {len(data)} bytes")
            success = self.piece_manager.piece_complete(piece_index, data)
            if not success:
                actual_hash = hashlib.sha1(data).hexdigest()
                expected_hash = self.piece_manager.piece_hashes[piece_index]
                logging.error(f"Hash mismatch for piece {piece_index}: expected {expected_hash}, got {actual_hash}")
            return success
        except Exception as e:
            logging.error(f"Download error for piece {piece_index}: {e}")
            return False

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    # Commented out bitfield methods to restore original behavior
    """
    def send_bitfield(self):
        try:
            bitfield = bytearray((self.piece_manager.total_pieces + 7) // 8)
            for i, have in enumerate(self.piece_manager.have_pieces):
                if have:
                    bitfield[i // 8] |= 1 << (7 - (i % 8))
            self.sock.send(f"BITFIELD:{bitfield.hex()}".encode())
            logging.info(f"Sent bitfield to {self.peer_id}")
        except Exception as e:
            logging.error(f"Failed to send bitfield to {self.peer_id}: {e}")

    def receive_bitfield(self):
        try:
            self.sock.settimeout(2)
            data = self.sock.recv(1024).decode().strip()
            if data.startswith("BITFIELD:"):
                bitfield = bytes.fromhex(data.split(":")[1])
                pieces = [False] * self.piece_manager.total_pieces
                for i in range(self.piece_manager.total_pieces):
                    if i // 8 < len(bitfield):
                        pieces[i] = bool(bitfield[i // 8] & (1 << (7 - (i % 8))))
                logging.info(f"Received bitfield from {self.peer_id}: {pieces}")
                return pieces
            logging.debug(f"No bitfield received from {self.peer_id}")
        except Exception as e:
            logging.error(f"Bitfield receive error from {self.peer_id}: {e}")
        return None
    """