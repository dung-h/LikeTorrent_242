# File: client.py
import shutil
import sqlite3
import socket
import json
import threading
import hashlib
import time
import os
import requests
from metainfo import Metainfo
from piece_manager import PieceManager
from peer import Peer
from config import TRACKER_PORT, PEER_PORT
import config
class TorrentClient:
    def __init__(self, torrent_file, is_seeder=False):
        self.db = sqlite3.connect('torrent.db')
        self.init_db()
        self.metainfo = Metainfo.load(torrent_file)
        self.peer_id = hashlib.sha1(str(time.time()).encode()).hexdigest()[:20]
        self.piece_manager = PieceManager(self.metainfo.to_dict(), is_seeder, self.db, client_peer_id=self.peer_id)
        self.peers = []
        self.state = 'seeding' if is_seeder else 'downloading'
        
        # Create socket first
        self.upload_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.upload_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Then find port
        self.port = self.find_port()
        
        self.upload_server.listen(5)
        self.running = True
        self.update_db_state()


    def init_db(self):
        c = self.db.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS peers (
            peer_id TEXT PRIMARY KEY,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            state TEXT NOT NULL,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS peer_torrents (
            peer_id TEXT,
            torrent_hash TEXT,
            pieces_owned TEXT NOT NULL,
            downloaded_bytes INTEGER DEFAULT 0,
            state TEXT NOT NULL,
            PRIMARY KEY (peer_id, torrent_hash),
            FOREIGN KEY (peer_id) REFERENCES peers(peer_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS peer_interactions (
            interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_peer_id TEXT NOT NULL,
            target_peer_id TEXT NOT NULL,
            torrent_hash TEXT NOT NULL,
            piece_index INTEGER,
            bytes_transferred INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_peer_id) REFERENCES peers(peer_id),
            FOREIGN KEY (target_peer_id) REFERENCES peers(peer_id)
        )''')
        self.db.commit()

    def find_port(self):
        port = PEER_PORT
        while port < PEER_PORT + 1000:
            try:
                self.upload_server.bind(('0.0.0.0', port))
                return port
            except OSError:
                port += 1
        raise RuntimeError("No available port")

    def update_db_state(self):
        # Create a thread-local connection to avoid cross-thread usage
        local_db = sqlite3.connect('torrent.db')
        with threading.Lock():
            c = local_db.cursor()
            c.execute('''INSERT OR REPLACE INTO peers (peer_id, ip, port, state)
                        VALUES (?, ?, ?, ?)''',
                    (self.peer_id, '127.0.0.1', self.port, self.state))
            pieces_owned = json.dumps(self.piece_manager.have_pieces)
            c.execute('''INSERT OR REPLACE INTO peer_torrents (peer_id, torrent_hash, pieces_owned, downloaded_bytes, state)
                        VALUES (?, ?, ?, ?, ?)''',
                    (self.peer_id, self.metainfo["torrent_hash"], pieces_owned,
                    sum(self.piece_manager.have_pieces) * self.metainfo["piece_length"], self.state))
            local_db.commit()
            local_db.close()

    def contact_tracker(self, event="started"):
        try:
            tracker_url = f"{self.metainfo['tracker'].rstrip('/')}/announce"
            if self.state == 'seeding':  # Override for seeders
                event = 'completed'
            params = {
                "torrent_hash": self.metainfo["torrent_hash"],
                "peer_id": self.peer_id,
                "port": self.port,
                "downloaded": sum(self.piece_manager.have_pieces) * self.metainfo["piece_length"],
                "event": event,
                "magnet": f"magnet:?xt=urn:btih:{self.metainfo['torrent_hash']}&tr={self.metainfo['tracker']}"
            }
            print(f"Contacting tracker with params: {params}")
            response = requests.get(tracker_url, params=params, timeout=30)
            if response.status_code == 200:
                self.peers = response.json()["peers"]
                print(f"Received peers: {self.peers}")
                self.state = {'started': 'downloading', 'completed': 'seeding', 'stopped': 'stopped'}.get(event, self.state)
                self.update_db_state()
            if hasattr(self, 'test_mode') and self.test_mode:
                self.peers = [{"peer_id": "test_seeder", "ip": "localhost", "port": 6881}]
                print(f"TEST MODE: Using test seeder at port 6881")
        except Exception as e:
            print(f"Tracker error: {e}")
            
    def start_download(self):
        self.state = 'downloading'
        self.contact_tracker("started")
        
        print(f"Starting download with {len(self.peers)} peers")
        print(f"Piece status: {self.piece_manager.have_pieces}")
        
        missing_pieces = self.piece_manager.missing_pieces()
        if not missing_pieces:
            print("No missing pieces to download!")
            if self.piece_manager.all_pieces_downloaded():
                self.state = 'seeding'
                self.contact_tracker("completed")
            self.update_db_state()
            return
        
        print(f"Need to download {len(missing_pieces)} pieces")
        
        max_retries = 3
        for peer_info in self.peers:
            if peer_info["peer_id"] == self.peer_id:
                continue
            peer = Peer(peer_info["peer_id"], peer_info["ip"], peer_info["port"], self.piece_manager, self.db)
            if peer.connect():
                for piece_index in self.piece_manager.missing_pieces():
                    retries = 0
                    success = False
                    while retries < max_retries and not success:
                        print(f"Downloading piece {piece_index} from {peer_info['peer_id']} (attempt {retries + 1}/{max_retries})")
                        success = peer.download_piece(piece_index, self.peer_id)
                        if not success:
                            print(f"Failed to download piece {piece_index}")
                            retries += 1
                            peer.close()
                            if retries < max_retries:
                                peer = Peer(peer_info["peer_id"], peer_info["ip"], peer_info["port"], self.piece_manager, self.db)
                                if not peer.connect():
                                    print(f"Reconnection to {peer_info['peer_id']} failed")
                                    break
                    if not success:
                        print(f"Giving up on piece {piece_index} after {max_retries} attempts")
                    # Close and reconnect for next piece
                    peer.close()
                    if self.piece_manager.missing_pieces():
                        peer = Peer(peer_info["peer_id"], peer_info["ip"], peer_info["port"], self.piece_manager, self.db)
                        if not peer.connect():
                            print(f"Reconnection to {peer_info['peer_id']} failed")
                            break
                
                peer.close()
        
        if self.piece_manager.all_pieces_downloaded():
            self.state = 'seeding'
            self.contact_tracker("completed")
        self.update_db_state()

    def handle_upload(self, conn, addr):
        try:
            conn.settimeout(10)
            print(f"New upload connection from {addr}")
            data = conn.recv(1024).decode().strip()
            print(f"Seeder received: {data}")
            
            if "ESTABLISH" in data:
                print(f"Sending ESTABLISHED response")
                conn.send("ESTABLISHED".encode())
                
                data = conn.recv(1024).decode().strip()
                print(f"Seeder received request: {data}")
                
                if "REQUEST:" in data:
                    piece_index = int(data.split(":")[1])
                    file_path = os.path.join(self.piece_manager.download_dir, self.metainfo["files"][0]["path"])
                    print(f"Looking for file at: {file_path}, exists: {os.path.exists(file_path)}")
                    
                    if os.path.exists(file_path):
                        print(f"Sending piece {piece_index}")
                        expected_size = self.piece_manager.expected_piece_length(piece_index)
                        with open(file_path, "rb") as f:
                            f.seek(piece_index * self.metainfo["piece_length"])
                            piece_data = f.read(expected_size)
                            print(f"Read {len(piece_data)} bytes from file")
                            
                            import hashlib
                            piece_hash = hashlib.sha1(piece_data).hexdigest()
                            expected_hash = self.metainfo["pieces"][piece_index]
                            print(f"Seeder calculated hash: {piece_hash}")
                            print(f"Expected hash: {expected_hash}")
                            print(f"Hash match: {piece_hash == expected_hash}")
                            
                            total_sent = 0
                            chunk_size = 4096
                            for i in range(0, len(piece_data), chunk_size):
                                chunk = piece_data[i:i+chunk_size]
                                bytes_sent = conn.send(chunk)
                                total_sent += bytes_sent
                                print(f"Sent chunk of {bytes_sent} bytes, total: {total_sent}/{len(piece_data)}")
                            
                            time.sleep(0.1)
        except Exception as e:
            print(f"Upload error: {e}")
        finally:
            time.sleep(0.1)
            conn.close()

    def start_upload(self):
        for file_info in self.metainfo["files"]:
            path = os.path.join(self.piece_manager.download_dir, file_info["path"])
            if os.path.exists(path):
                print(f"File found: {path} ({os.path.getsize(path)} bytes)")
            else:
                print(f"WARNING: File not found: {path}")
                
                # Copy from original location if needed
                original_path = file_info["path"]
                if os.path.exists(original_path):
                    print(f"Found original file at {original_path}, copying...")
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    shutil.copy(original_path, path)
                    print(f"Copied file to {path}")
        self.state = 'seeding' if self.piece_manager.all_pieces_downloaded() else 'downloading'
        self.update_db_state()
        self.contact_tracker("started")
        try:
            while self.running:
                conn, addr = self.upload_server.accept()
                threading.Thread(target=self.handle_upload, args=(conn, addr)).start()
        except Exception:
            pass
        finally:
            self.upload_server.close()

    def pause(self):
        self.state = 'paused'
        self.update_db_state()

    def stop(self):
        self.state = 'stopped'
        self.running = False
        self.contact_tracker("stopped")
        self.update_db_state()
        self.upload_server.close()
        self.db.close()

    def resume(self):
        if self.state == 'paused':
            self.state = 'downloading'
            self.running = True
            threading.Thread(target=self.start_upload).start()
            self.start_download()
            self.update_db_state()
import argparse

def main():
    parser = argparse.ArgumentParser(description='BitTorrent-like client')
    parser.add_argument('torrent_file', help='Path to the torrent file')
    parser.add_argument('--seed', action='store_true', help='Run in seeder mode')
    parser.add_argument('--port', type=int, default=config.PEER_PORT, 
                        help='Port to listen on')
    
    args = parser.parse_args()
    
    client = TorrentClient(args.torrent_file, is_seeder=args.seed)
    client.port = args.port  # Override the default port
    
    if args.seed:
        client.start_upload()
    else:
        client.start_download()

if __name__ == "__main__":
    main()