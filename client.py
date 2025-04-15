# File: client.py
import socket
import threading
import os
import time
import hashlib
import requests
import random
import argparse
import queue
import logging
from config import PEER_PORT, PIECE_SIZE, DOWNLOAD_DIR
from peer import Peer
from piece_manager import PieceManager
from metainfo import parse_torrent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')

class PeerStats:
    def __init__(self, peer_id, ip, port):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.successes = 0
        self.failures = 0
        self.total_time = 0.0
        self.requests = 0
        self.weight = 1.0

    def update(self, success, elapsed_time):
        self.requests += 1
        if success:
            self.successes += 1
            self.total_time += elapsed_time
        else:
            self.failures += 1
        success_rate = self.successes / max(self.requests, 1)
        avg_time = (self.total_time / max(self.successes, 1)) if self.successes > 0 else 10.0
        self.weight = max(success_rate / max(avg_time, 0.1), 0.1)
        logging.info(f"Updated {self}")

    def __str__(self):
        return (f"Peer {self.peer_id} ({self.ip}:{self.port}): "
                f"Weight={self.weight:.2f}, Successes={self.successes}/{self.requests}")

class Client:
    def __init__(self, torrent_file, port=PEER_PORT):
        self.metainfo = self.load_metainfo(torrent_file)
        self.peer_id = self.generate_peer_id()
        self.piece_manager = PieceManager(self.metainfo, self.peer_id)
        self.state = 'stopped'
        self.running = True
        self.peers = []
        self.upload_server = None
        self.port = self.find_port(port)
        self.db_lock = threading.Lock()
        self.bytes_downloaded = 0
        self.last_speed_update = time.time()
        self.speed_lock = threading.Lock()
        self.active_connections = []  # Track peer connections
        logging.info(f"Client initialized on port {self.port}")

    def load_metainfo(self, torrent_file):
        return parse_torrent(torrent_file)

    def generate_peer_id(self):
        return ''.join(random.choices('0123456789abcdef', k=20))

    def find_port(self, start_port):
        port = start_port
        while True:
            try:
                self.upload_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.upload_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.upload_server.bind(('0.0.0.0', port))
                self.upload_server.listen(5)
                return port
            except:
                port += 1
                if port > start_port + 100:
                    raise RuntimeError("No available ports")

    def contact_tracker(self, event="started"):
        try:
            tracker_url = f"{self.metainfo['announce'].rstrip('/')}/announce"
            params = {
                "torrent_hash": self.metainfo["torrent_hash"],
                "peer_id": self.peer_id,
                "port": self.port,
                "downloaded": sum(self.piece_manager.have_pieces) * self.metainfo["piece_length"],
                "event": event,
                "magnet": f"magnet:?xt=urn:btih:{self.metainfo['torrent_hash']}&tr={self.metainfo['announce']}"
            }
            logging.info(f"Contacting tracker with params: {params}")
            response = requests.get(tracker_url, params=params, timeout=30)
            if response.status_code == 200:
                new_peers = response.json()["peers"]
                peer_ids = {p["peer_id"] for p in self.peers}
                self.peers.extend([p for p in new_peers if p["peer_id"] not in peer_ids and p["peer_id"] != self.peer_id])
                logging.info(f"Received peers: {[f'{p['ip']}:{p['port']}' for p in self.peers]}")
                self.state = {'started': 'downloading', 'completed': 'seeding', 'stopped': 'stopped'}.get(event, self.state)
            else:
                logging.warning(f"Tracker returned {response.status_code}: {response.text}")
        except Exception as e:
            logging.error(f"Tracker error: {e}")

    def check_file_exists(self):
        for file_info in self.metainfo["files"]:
            path = os.path.join(self.piece_manager.download_dir, file_info["path"])
            if not os.path.exists(path):
                logging.info(f"File missing: {path}")
                return False
        complete = self.piece_manager.all_pieces_downloaded()
        logging.info(f"All pieces complete: {complete}")
        return complete

    def get_speed(self):
        with self.speed_lock:
            elapsed = time.time() - self.last_speed_update
            if elapsed > 0:
                speed = self.bytes_downloaded / elapsed / 1024
                self.bytes_downloaded = 0
                self.last_speed_update = time.time()
                return speed
            return 0.0

    def start_download(self):
        if not self.running:
            return
        self.state = 'downloading'
        self.contact_tracker("started")
        
        logging.info(f"Starting download with {len(self.peers)} peers")
        missing_pieces = self.piece_manager.missing_pieces()
        logging.info(f"Piece status: {self.piece_manager.have_pieces}")
        logging.info(f"Missing pieces: {len(missing_pieces)} pieces")
        
        if not missing_pieces:
            logging.info("No missing pieces to download!")
            if self.piece_manager.all_pieces_downloaded():
                self.state = 'seeding'
                self.contact_tracker("completed")
            return
        
        logging.info(f"Need to download {len(missing_pieces)} pieces")
        
        peer_stats = {
            p["peer_id"]: PeerStats(p["peer_id"], p["ip"], p["port"])
            for p in self.peers if p["peer_id"] != self.peer_id
        }
        
        piece_queue = queue.Queue()
        requested_pieces = set()
        queue_lock = threading.Lock()
        
        for piece_index in missing_pieces:
            piece_queue.put(piece_index)
        
        max_retries = 3
        max_concurrent = 3
        active_threads = []
        
        def update_peers():
            while self.state == 'downloading' and self.running:
                self.contact_tracker()
                with queue_lock:
                    for peer in self.peers:
                        if peer["peer_id"] != self.peer_id and peer["peer_id"] not in peer_stats:
                            peer_stats[peer["peer_id"]] = PeerStats(peer["peer_id"], peer["ip"], peer["port"])
                            logging.info(f"Added new peer to stats: {peer['peer_id']} ({peer['ip']}:{peer['port']})")
                time.sleep(30)
        
        peer_update_thread = threading.Thread(target=update_peers, daemon=True)
        peer_update_thread.start()
        
        def download_worker():
            while not piece_queue.empty() and self.running:
                with queue_lock:
                    if piece_queue.empty():
                        break
                    try:
                        piece_index = piece_queue.get_nowait()
                        if piece_index in requested_pieces:
                            piece_queue.put(piece_index)
                            continue
                        requested_pieces.add(piece_index)
                    except queue.Empty:
                        break
                
                available_peers = list(peer_stats.values())
                random.shuffle(available_peers)
                success = False
                
                for selected_peer in available_peers:
                    if not self.running:
                        break
                    peer_info = {
                        "peer_id": selected_peer.peer_id,
                        "ip": selected_peer.ip,
                        "port": selected_peer.port
                    }
                    logging.info(f"Attempting to download piece {piece_index} from {peer_info['peer_id']} ({peer_info['ip']}:{peer_info['port']})")
                    
                    retries = 0
                    while retries < max_retries and not success and self.running:
                        peer = Peer(peer_info["peer_id"], peer_info["ip"], peer_info["port"], self.piece_manager)
                        if peer.connect():
                            self.active_connections.append(peer)
                            start_time = time.time()
                            try:
                                success = peer.download_piece(piece_index, self.peer_id)
                                elapsed_time = time.time() - start_time
                                with self.db_lock:
                                    peer_stats[peer_info["peer_id"]].update(success, elapsed_time)
                                if success:
                                    with self.speed_lock:
                                        piece_size = self.piece_manager.expected_piece_length(piece_index)
                                        self.bytes_downloaded += piece_size
                                    logging.info(f"Successfully downloaded piece {piece_index} from {peer_info['peer_id']} in {elapsed_time:.2f}s")
                                else:
                                    logging.warning(f"Failed to download piece {piece_index} from {peer_info['peer_id']}")
                            except Exception as e:
                                logging.error(f"Error downloading piece {piece_index} from {peer_info['peer_id']}: {e}")
                                with self.db_lock:
                                    peer_stats[peer_info["peer_id"]].update(False, 0)
                                retries += 1
                            peer.close()
                            self.active_connections.remove(peer)
                        else:
                            logging.warning(f"Failed to connect to {peer_info['peer_id']} ({peer_info['ip']}:{peer_info['port']})")
                            with self.db_lock:
                                peer_stats[peer_info["peer_id"]].update(False, 0)
                            retries += 1
                            time.sleep(1)
                    
                    if success:
                        break
                
                with queue_lock:
                    requested_pieces.discard(piece_index)
                    if not success and self.running:
                        logging.warning(f"Failed to download piece {piece_index} after {max_retries} retries, requeuing")
                        piece_queue.put(piece_index)
        
        for i in range(min(max_concurrent, len(self.peers))):
            t = threading.Thread(target=download_worker, name=f"DownloadWorker-{i}")
            t.start()
            active_threads.append(t)
        
        for t in active_threads:
            t.join()
        
        if self.piece_manager.all_pieces_downloaded() and self.running:
            self.state = 'seeding'
            self.contact_tracker("completed")
            logging.info("Download completed, switching to seeding mode")

    def handle_upload(self, conn, addr):
        try:
            conn.settimeout(10)
            logging.info(f"New upload connection from {addr}")
            data = conn.recv(1024).decode().strip()
            logging.info(f"Seeder received: {data}")
            
            if "ESTABLISH" in data:
                logging.info(f"Sending ESTABLISHED response")
                conn.send("ESTABLISHED".encode())
                
                data = conn.recv(1024).decode().strip()
                logging.info(f"Seeder received request: {data}")
                
                if "REQUEST:" in data:
                    piece_index = int(data.split(":")[1])
                    file_path = os.path.join(self.piece_manager.download_dir, self.metainfo["files"][0]["path"])
                    logging.info(f"Looking for file at: {file_path}, exists: {os.path.exists(file_path)}")
                    
                    if os.path.exists(file_path):
                        logging.info(f"Sending piece {piece_index}")
                        expected_size = self.piece_manager.expected_piece_length(piece_index)
                        with open(file_path, "rb") as f:
                            f.seek(piece_index * self.metainfo["piece_length"])
                            piece_data = f.read(expected_size)
                            logging.info(f"Read {len(piece_data)} bytes from file")
                            
                            piece_hash = hashlib.sha1(piece_data).hexdigest()
                            expected_hash = self.metainfo["pieces"][piece_index]
                            logging.info(f"Seeder calculated hash: {piece_hash}, Expected hash: {expected_hash}, Match: {piece_hash == expected_hash}")
                            
                            total_sent = 0
                            chunk_size = 4096
                            for i in range(0, len(piece_data), chunk_size):
                                if not self.running:
                                    break
                                chunk = piece_data[i:i+chunk_size]
                                bytes_sent = conn.send(chunk)
                                total_sent += bytes_sent
                            
                            time.sleep(0.1)
        except Exception as e:
            logging.error(f"Upload error: {e}")
        finally:
            time.sleep(0.1)
            conn.close()

    def listen_for_requests(self):
        self.state = 'seeding' if self.check_file_exists() else 'idle'
        self.contact_tracker("started")
        logging.info(f"Client in {self.state} mode, listening on port {self.port}")
        try:
            while self.running:
                self.upload_server.settimeout(1.0)
                try:
                    conn, addr = self.upload_server.accept()
                    threading.Thread(target=self.handle_upload, args=(conn, addr)).start()
                except socket.timeout:
                    continue
        except Exception as e:
            logging.error(f"Listen error: {e}")
        finally:
            self.upload_server.close()
            self.contact_tracker("stopped")

    def stop(self):
        self.running = False
        self.state = 'stopped'
        self.contact_tracker("stopped")
        if self.upload_server:
            self.upload_server.close()
        for peer in self.active_connections[:]:
            try:
                peer.close()
            except:
                pass
        self.active_connections.clear()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("torrent_file")
    parser.add_argument("--download", action="store_true", help="Start downloading the torrent")
    parser.add_argument("--no-seed", action="store_true", help="Disable seeding even if file exists")
    parser.add_argument("--port", type=int, default=PEER_PORT)
    args = parser.parse_args()
    
    client = Client(args.torrent_file, args.port)
    try:
        if args.download:
            client.start_download()
            if not args.no_seed:
                client.listen_for_requests()
        elif not args.no_seed:
            client.listen_for_requests()
        else:
            logging.info("No download or seeding requested, exiting")
    except KeyboardInterrupt:
        logging.info("Shutting down client...")
        client.stop()