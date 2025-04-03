# File: client.py
import socket
import json
import threading
import hashlib
import time
from metainfo import Metainfo
from piece_manager import PieceManager
from peer import Peer
from config import TRACKER_PORT, PEER_PORT
import os
import requests

class TorrentClient:
    def __init__(self, torrent_file, is_seeder=False):
        self.metainfo = Metainfo.load(torrent_file)
        self.peer_id = hashlib.sha1(str(time.time()).encode()).hexdigest()[:20]
        self.piece_manager = PieceManager(self.metainfo.to_dict(), is_seeder=is_seeder)
        self.peers = []
        
        # Find an available port
        self.port = PEER_PORT
        self.upload_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Local test
        self.upload_server.settimeout(1)
    
        # This allows socket address reuse - CRITICAL for local testing
        self.upload_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # End

        bound = False
        while not bound and self.port < PEER_PORT + 1000:  # Try 1000 ports
            try:
                self.upload_server.bind(('0.0.0.0', self.port))
                bound = True
                print(f"Client bound to port {self.port}")
            except OSError:
                self.port += 1
                self.upload_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        if not bound:
            raise RuntimeError("Could not find an available port")
        
        self.upload_server.listen(5)
        self.running = True

    # def contact_tracker(self):
    #     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     # sock.connect(('localhost', TRACKER_PORT))
    #     sock.connect(('5b53c0d2b81983.lhr.life', TRACKER_PORT))
    #     request = {
    #         "torrent_hash": self.metainfo["torrent_hash"],
    #         "peer_id": self.peer_id,
    #         "port": self.port,  # Use the dynamically assigned port
    #         "downloaded": sum(self.piece_manager.have_pieces) * self.metainfo["piece_length"]
    #     }
    #     sock.send(json.dumps(request).encode())
    #     response = json.loads(sock.recv(1024).decode())
    #     self.peers = response["peers"]
    #     sock.close()

    def contact_tracker(self):
        try:
            base_url = self.metainfo["tracker"].rstrip('/')
            tracker_url = f"{base_url}/announce"
            print(f"Connecting to tracker at {tracker_url}")
            
            # Use GET instead of POST (since GET is more compatible with proxies)
            params = {
                "torrent_hash": self.metainfo["torrent_hash"],
                "peer_id": self.peer_id,
                "port": self.port,
                "downloaded": sum(self.piece_manager.have_pieces) * self.metainfo["piece_length"]
            }
            
            headers = {
                "User-Agent": "LikeTorrent/1.0",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            print("Sending tracker request:", params)
            response = requests.get(tracker_url, params=params, headers=headers, timeout=30)
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                resp_data = response.json()
                print(f"Tracker response: {resp_data}")
                self.peers = resp_data["peers"]
                print(f"Received {len(self.peers)} peers from tracker")
            else:
                print(f"Error response from tracker: {response.status_code}")
                print(f"Response text: {response.text}")
                
        except Exception as e:
            print(f"Error connecting to tracker: {e}")

    def start_download(self):
        self.contact_tracker()
        threads = []
        
        for peer_info in self.peers:
            if peer_info["peer_id"] == self.peer_id or (
                peer_info["ip"] == "127.0.0.1" and peer_info["port"] == self.port):
                    print(f"Skipping self connection to {peer_info['peer_id']}")
                    continue
                
            peer = Peer(peer_info["peer_id"], peer_info["ip"], peer_info["port"], self.piece_manager)
            if peer.connect():
                peer_threads = []
                for piece_index in self.piece_manager.missing_pieces():
                    t = threading.Thread(target=peer.download_piece, args=(piece_index,))
                    peer_threads.append(t)
                    threads.append(t)
                    t.start()
                    
                # Wait for all downloads from this peer to complete before closing
                for t in peer_threads:
                    t.join()
                    
                # Now it's safe to close the connection
                peer.close()
                
        # No need to join threads here as we've already joined them above
    def handle_upload(self, conn, addr):
        try:
            file_path = self.metainfo["files"][0]["path"]
            print(f"Original file path: {file_path}")
            print(f"File exists at original location: {os.path.exists(file_path)}")
            print(f"File exists in downloads: {os.path.exists(os.path.join('downloads', file_path))}")
            
            # Keep the connection open for multiple messages
            conn.settimeout(10)
            data = conn.recv(1024).decode()
            print(f"Upload request from {addr}: {data}")
            
            if "ESTABLISH" in data:
                conn.send("ESTABLISHED".encode())
                print(f"Connection established with {addr}")
                
                # Wait for the REQUEST message after ESTABLISH
                try:
                    data = conn.recv(1024).decode()
                    print(f"Follow-up request from {addr}: {data}")
                    
                    if "REQUEST" in data:
                        piece_index = int(data.split(":")[1])
                        print(f"Received request for piece {piece_index} from {addr}")
                        
                        # Determine file path - USE ABSOLUTE PATH for clarity
                        actual_path = os.path.abspath(file_path)
                        print(f"Looking for file at: {actual_path}")
                        
                        # For seeders, prefer original file, not downloads
                        if os.path.exists(actual_path):
                            print(f"Using original file: {actual_path}")
                            with open(actual_path, "rb") as f:
                                f.seek(piece_index * self.metainfo["piece_length"])
                                piece_data = f.read(self.metainfo["piece_length"])
                                print(f"Read {len(piece_data)} bytes for piece {piece_index}")
                                
                                # Send in smaller chunks with explicit flush
                                chunk_size = 1024
                                total_sent = 0
                                for i in range(0, len(piece_data), chunk_size):
                                    chunk = piece_data[i:i+chunk_size]
                                    bytes_sent = conn.send(chunk)
                                    total_sent += bytes_sent
                                    print(f"Sent {bytes_sent} bytes, total: {total_sent}/{len(piece_data)}")
                                    time.sleep(0.01)  # Small delay to prevent overwhelming
                                
                                print(f"COMPLETE: Sent {total_sent} bytes for piece {piece_index}")
                except Exception as e:
                    print(f"Error while handling request: {e}")
            
        except Exception as e:
            print(f"Upload error from {addr}: {e}")
        finally:
            # Give time before closing
            time.sleep(0.5)
            print(f"Closing connection with {addr}")
            conn.close()
            
    
    def start_upload(self):
        print(f"Starting upload server on port {self.port}")
        try:
            while self.running:
                try:
                    conn, addr = self.upload_server.accept()
                    print(f"New upload connection from {addr}")
                    threading.Thread(target=self.handle_upload, args=(conn, addr)).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:  # Only print error if we're still supposed to be running
                        print(f"Error accepting connection: {e}")
        except KeyboardInterrupt:
            print("Upload server stopped by user")
        finally:
            self.upload_server.close()
            
    def stop(self):
        self.running = False
        self.upload_server.close()

if __name__ == "__main__":
    client = TorrentClient("sample.torrent")
    threading.Thread(target=client.start_upload).start()
    client.start_download()