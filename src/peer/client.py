# File: src/peer/client.py
import sys
import os
import threading
import time
import logging
import requests
import json
import socket
import random
import urllib.parse
import queue
import argparse

# Add the parent directory to path for importing from peer module
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(current_dir)))  # Add project root to path
sys.path.append(current_dir)  # Add current directory to path

from peer import Peer
from piece_manager import PieceManager
from metainfo import parse_torrent

PEER_PORT = 6881
EXPECTED_PORT_RANGE = range(6881, 6891)  # Standard BitTorrent ports
EPHEMERAL_PORT_RANGE = range(49152, 65536)  # Typical ephemeral ports

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        self.pieces_downloaded = 0
        self.pieces_uploaded = 0
        self.bytes_downloaded = 0
        self.bytes_uploaded = 0
        self.last_update = time.time()

    def update_download(self, success, elapsed_time, piece_size):
        self.requests += 1
        if success:
            self.successes += 1
            self.total_time += elapsed_time
            self.pieces_downloaded += 1
            self.bytes_downloaded += piece_size
        else:
            self.failures += 1
        success_rate = self.successes / max(self.requests, 1)
        avg_time = (self.total_time / max(self.successes, 1)) if self.successes > 0 else 10.0
        self.weight = max(success_rate / max(avg_time, 0.1), 0.1)
        self.last_update = time.time()
        logging.info(f"Updated {self}")

    def update_upload(self, piece_size):
        self.pieces_uploaded += 1
        self.bytes_uploaded += piece_size
        self.last_update = time.time()

    def get_download_speed(self):
        elapsed = time.time() - self.last_update
        if elapsed > 0.05:
            speed = self.bytes_downloaded / elapsed / 1024
            self.bytes_downloaded = 0
            self.last_update = time.time()
            return min(speed, 1024 * 1024)  # Cap at 1 GB/s
        return 0.0

    def get_upload_speed(self):
        elapsed = time.time() - self.last_update
        if elapsed > 0.05:
            speed = self.bytes_uploaded / elapsed / 1024
            self.bytes_uploaded = 0
            self.last_update = time.time()
            return min(speed, 1024 * 1024)  # Cap at 1 GB/s
        return 0.0

    def __str__(self):
        return (f"Peer {self.peer_id} ({self.ip}:{self.port}): "
                f"Weight={self.weight:.2f}, Successes={self.successes}/{self.requests}, "
                f"Pieces Uploaded={self.pieces_uploaded}")

class Client:
    def __init__(self, torrent_file, base_path, port=PEER_PORT):
        self.metainfo = self.load_metainfo(torrent_file)
        self.base_path = base_path
        self.peer_id = self.generate_peer_id()
        self.piece_manager = PieceManager(self.metainfo, self.peer_id, base_path)
        self.state = 'stopped'
        self.running = True
        self.paused = False
        self.peers = []
        self.upload_server = None
        self.port = self.find_port(port)
        self.db_lock = threading.Lock()
        self.bytes_downloaded = 0
        self.bytes_uploaded = 0
        self.temp_bytes_downloaded = 0
        self.temp_bytes_uploaded = 0
        self.last_speed_update = time.time()
        self.speed_lock = threading.Lock()
        self.active_connections = []
        self.peer_stats = {}
        self.peer_priority = queue.Queue()
        logging.info(f"Client initialized: torrent={torrent_file}, base_path={base_path}, port={self.port}")
        threading.Thread(target=self.cleanup_peer_stats, daemon=True).start()

    def load_metainfo(self, torrent_file):
        return parse_torrent(torrent_file)

    def generate_peer_id(self):
        return ''.join(random.choices('0123456789abcdef', k=20))

    def find_port(self, start_port):
        port = start_port
        max_attempts = 10
        attempts = 0
        while attempts < max_attempts:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', port))
                sock.listen(5)
                sock.settimeout(0.1)
                try:
                    sock.accept()
                except socket.timeout:
                    self.upload_server = sock
                    logging.info(f"Successfully bound to port {port}")
                    return port
            except OSError as e:
                logging.warning(f"Failed to bind to port {port}: {e}")
                if sock:
                    sock.close()
                port += 1
            except Exception as e:
                logging.error(f"Unexpected error while binding to port {port}: {e}")
                if sock:
                    sock.close()
                port += 1
            finally:
                attempts += 1
                if attempts >= max_attempts:
                    raise RuntimeError(f"No available ports found after trying {max_attempts} ports")
        raise RuntimeError("No available ports")

    def contact_tracker(self, event="started"):
        max_retries = 3
        retry_delay = 10
        tracker_url = self.metainfo.get('announce', '')
        if not tracker_url:
            logging.error("No tracker URL found in torrent file")
            return
        for attempt in range(max_retries):
            try:
                magnet = f"magnet:?xt=urn:btih:{self.metainfo['torrent_hash']}&tr={urllib.parse.quote(self.metainfo['announce'])}"
                params = {
                    "torrent_hash": self.metainfo["torrent_hash"],
                    "peer_id": self.peer_id,
                    "port": self.port,
                    "downloaded": sum(self.piece_manager.have_pieces) * self.metainfo["piece_length"],
                    "event": event,
                    "seeding": self.piece_manager.all_pieces_downloaded(),
                    "magnet": magnet
                }
                logging.info(f"Contacting tracker {tracker_url}/announce with params: {params}")
                response = requests.get(tracker_url + "/announce", params=params, timeout=30)
                if response.status_code == 200:
                    new_peers = response.json().get("peers", [])
                    logging.info(f"Raw tracker response: {new_peers}")
                    self.peers.clear()  # Clear old peers
                    peer_ids = set()
                    added_peers = []
                    for p in new_peers[:4]:  # Limit to 4 peers
                        if p["peer_id"] == self.peer_id:
                            logging.debug(f"Skipping own peer: {p['peer_id']}")
                            continue
                        if p["peer_id"] in peer_ids:
                            logging.debug(f"Skipping duplicate peer: {p['peer_id']}")
                            continue
                        port = p.get("port", 0)
                        if port in EXPECTED_PORT_RANGE:  # 6881–6890
                            logging.info(f"Accepting peer {p['peer_id']} on expected port {port}")
                            self.peers.append(p)
                            added_peers.append(p)
                            peer_ids.add(p["peer_id"])
                        elif port in EPHEMERAL_PORT_RANGE:  # 49152–65535
                            logging.info(f"Accepting peer {p['peer_id']} on ephemeral port {port}")
                            self.peers.append(p)
                            added_peers.append(p)
                            peer_ids.add(p["peer_id"])
                        else:
                            logging.warning(f"Skipping peer with suspicious port: {p['peer_id']} ({p['ip']}:{port})")
                    logging.info(f"Added peers: {[f'{p['ip']}:{p['port']}' for p in added_peers]}")
                    for peer in added_peers:
                        if peer["peer_id"] not in self.peer_stats:
                            self.peer_stats[peer["peer_id"]] = PeerStats(peer["peer_id"], peer["ip"], peer["port"])
                        if not self.peer_priority.full():
                            self.peer_priority.put(peer["peer_id"])
                    self.state = {'started': 'downloading', 'completed': 'seeding', 'stopped': 'stopped'}.get(event, self.state)
                    if not added_peers and event != "stopped":
                        logging.warning("No valid peers added, retrying...")
                        continue
                    return
                else:
                    logging.warning(f"Tracker attempt {attempt + 1} returned {response.status_code}: {response.text}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Tracker attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logging.info(f"Retrying tracker in {retry_delay} seconds...")
                time.sleep(retry_delay)
        logging.error(f"Failed to contact tracker after {max_retries} attempts")
    def check_file_exists(self):
        for file_info in self.metainfo["files"]:
            path = os.path.normpath(os.path.join(self.base_path, file_info["path"]))
            if not os.path.exists(path):
                logging.info(f"File missing: {path}")
                return False
        complete = self.piece_manager.all_pieces_downloaded()
        logging.info(f"All pieces complete: {complete}")
        return complete

    def get_speed(self, upload=False):
        with self.speed_lock:
            elapsed = time.time() - self.last_speed_update
            speed = 0.0
            if elapsed > 0.05:
                speed = (self.temp_bytes_uploaded if upload else self.temp_bytes_downloaded) / elapsed / 1024
                logging.info(f"Speed calc: {self.temp_bytes_uploaded if upload else self.temp_bytes_downloaded} bytes / {elapsed:.2f}s = {speed:.2f} KB/s")
            if upload:
                self.temp_bytes_uploaded = 0
            else:
                self.temp_bytes_downloaded = 0
            self.last_speed_update = time.time()
            return min(speed, 1024 * 1024)  # Cap at 1 GB/s

    def cleanup_peer_stats(self):
        while self.running:
            with self.db_lock:
                active_peer_ids = {p["peer_id"] for p in self.peers}
                self.peer_stats = {pid: stats for pid, stats in self.peer_stats.items()
                                  if pid in active_peer_ids and (time.time() - stats.last_update) < 10}
            time.sleep(5)

    def update_peers(self):
        while self.state == 'downloading' and self.running:
            self.contact_tracker()
            time.sleep(15)  # Faster updates for new seeders

    def start_download(self):
        if not self.running:
            return
        self.state = 'downloading'
        self.contact_tracker("started")
        
        logging.info(f"Starting download to {self.base_path} with {len(self.peers)} peers")
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
        
        piece_queue = queue.Queue()
        requested_pieces = set()
        queue_lock = threading.Lock()
        
        for piece_index in missing_pieces:
            piece_queue.put(piece_index)
        
        max_retries = 3
        max_concurrent = 2
        active_threads = []
        
        peer_update_thread = threading.Thread(target=self.update_peers, daemon=True)
        peer_update_thread.start()
        
        def download_worker():
            while not piece_queue.empty() and self.running and not self.paused:
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
                
                available_peers = [(Peer(peer["peer_id"], peer["ip"], peer["port"], self.piece_manager), 
                                  self.peer_stats[peer["peer_id"]]) for peer in self.peers]
                
                if not available_peers:
                    with queue_lock:
                        requested_pieces.discard(piece_index)
                        piece_queue.put(piece_index)
                    time.sleep(1)
                    continue
                
                # Round-robin peer selection
                peer_id = None
                try:
                    peer_id = self.peer_priority.get_nowait()
                    self.peer_priority.put(peer_id)
                except queue.Empty:
                    for peer in self.peers:
                        self.peer_priority.put(peer["peer_id"])
                    peer_id = self.peer_priority.get_nowait()
                    self.peer_priority.put(peer_id)
                
                selected_peers = [(p, s) for p, s in available_peers if s.peer_id == peer_id]
                if not selected_peers:
                    selected_peers = available_peers  # Fallback to any peer
                
                for peer, selected_peer in selected_peers:
                    if not self.running or self.paused:
                        break
                    # Prefer peers with more uploads (likely seeders)
                    if selected_peer.pieces_uploaded > 0:
                        logging.debug(f"Prioritizing peer {selected_peer.peer_id} with {selected_peer.pieces_uploaded} uploads")
                    retries = 0
                    success = False
                    while retries < max_retries and not success and self.running and not self.paused:
                        logging.info(f"Trying to download piece {piece_index} from {selected_peer.peer_id} ({selected_peer.ip}:{selected_peer.port})")
                        if peer.connect():
                            self.active_connections.append(peer)
                            start_time = time.time()
                            try:
                                success = peer.download_piece(piece_index, self.peer_id)
                                elapsed_time = time.time() - start_time
                                with self.db_lock:
                                    piece_size = self.piece_manager.expected_piece_length(piece_index)
                                    self.peer_stats[selected_peer.peer_id].update_download(success, elapsed_time, piece_size)
                                if success:
                                    with self.speed_lock:
                                        self.temp_bytes_downloaded += piece_size
                                    logging.info(f"Successfully downloaded piece {piece_index} from {selected_peer.peer_id} in {elapsed_time:.2f}s, {piece_size} bytes")
                                else:
                                    logging.warning(f"Failed to download piece {piece_index} from {selected_peer.peer_id}")
                            except Exception as e:
                                logging.error(f"Error downloading piece {piece_index} from {selected_peer.peer_id}: {e}")
                                with self.db_lock:
                                    self.peer_stats[selected_peer.peer_id].update_download(False, 0, 0)
                                retries += 1
                            peer.close()
                            if peer in self.active_connections:
                                self.active_connections.remove(peer)
                        else:
                            logging.warning(f"Failed to connect to {selected_peer.peer_id} ({selected_peer.ip}:{selected_peer.port})")
                            with self.db_lock:
                                self.peer_stats[selected_peer.peer_id].update_download(False, 0, 0)
                            retries += 1
                            time.sleep(2)
                    
                    if success:
                        break
                    time.sleep(1)
                
                with queue_lock:
                    requested_pieces.discard(piece_index)
                    if not success and self.running and not self.paused:
                        logging.warning(f"Failed to download piece {piece_index} after {max_retries} retries, requeuing")
                        piece_queue.put(piece_index)
                        time.sleep(1)
        
        for i in range(min(max_concurrent, max(1, len(self.peers)))):
            t = threading.Thread(target=download_worker, name=f"DownloadWorker-{i}")
            t.start()
            active_threads.append(t)
        
        for t in active_threads:
            t.join()
        
        if self.piece_manager.all_pieces_downloaded() and self.running:
            self.state = 'seeding'
            self.contact_tracker("completed")
            logging.info(f"Download completed to {self.base_path}, switching to seeding mode")
            # Start seeding immediately
            threading.Thread(target=self.listen_for_requests, daemon=True).start()

    def handle_upload(self, conn, addr):
        try:
            port = addr[1]
            if port not in EXPECTED_PORT_RANGE and port not in EPHEMERAL_PORT_RANGE:
                logging.debug(f"Rejecting connection from suspicious port: {addr[0]}:{port}")
                return
            conn.settimeout(15)
            data = conn.recv(1024).decode().strip()
            if data != "ESTABLISH":
                logging.debug(f"Invalid initial message from {addr}: {data}")
                return
            conn.send("ESTABLISHED".encode())
            
            while self.running and not self.paused:
                try:
                    conn.settimeout(15)
                    data = conn.recv(1024).decode().strip()
                    if not data:
                        logging.debug(f"Empty request from {addr}, closing")
                        break
                    if not data.startswith("REQUEST:"):
                        logging.debug(f"Invalid request from {addr}: {data}")
                        continue
                    
                    try:
                        piece_index = int(data.split(":")[1])
                    except (IndexError, ValueError):
                        logging.debug(f"Malformed request from {addr}: {data}")
                        continue
                    
                    logging.info(f"New upload connection from {addr}")
                    logging.info(f"Seeder received request: {data}")
                    
                    peer_id = f"{addr[0]}:{addr[1]}"
                    read_start = time.time()
                    piece_data = self.piece_manager._read_piece(piece_index)
                    read_time = time.time() - read_start
                    logging.info(f"Read piece {piece_index} in {read_time:.2f}s")
                    if piece_data:
                        logging.info(f"Sending piece {piece_index} from {self.base_path}")
                        total_sent = 0
                        chunk_size = 4096
                        for i in range(0, len(piece_data), chunk_size):
                            if not self.running or self.paused:
                                break
                            chunk = piece_data[i:i+chunk_size]
                            try:
                                bytes_sent = conn.send(chunk)
                                total_sent += bytes_sent
                            except socket.error:
                                logging.warning(f"Failed to send chunk to {addr}")
                                break
                        
                        if total_sent == len(piece_data):
                            with self.speed_lock:
                                self.temp_bytes_uploaded += total_sent
                            if peer_id not in self.peer_stats:
                                self.peer_stats[peer_id] = PeerStats(peer_id, addr[0], addr[1])
                            self.peer_stats[peer_id].update_upload(total_sent)
                            logging.info(f"Successfully sent piece {piece_index} to {addr}: {total_sent} bytes")
                        else:
                            logging.warning(f"Failed to send complete piece {piece_index}: sent {total_sent}/{len(piece_data)}")
                    else:
                        logging.warning(f"Piece {piece_index} not available")
                except socket.timeout:
                    logging.debug(f"Timeout waiting for request from {addr}")
                    break
                except Exception as e:
                    logging.error(f"Upload request error from {addr}: {e}")
                    break
        except Exception as e:
            logging.debug(f"Upload error from {addr}: {e}")
        finally:
            conn.close()

    def listen_for_requests(self):
        if not self.check_file_exists():
            logging.info(f"Cannot seed: files missing at {self.base_path}")
            self.state = 'idle'
            return
        self.state = 'seeding'
        self.contact_tracker("started")
        logging.info(f"Client seeding from {self.base_path}, listening on port {self.port}")
        
        def update_peers():
            while self.state == 'seeding' and self.running:
                self.contact_tracker()
                time.sleep(15)
        
        peer_update_thread = threading.Thread(target=self.update_peers, daemon=True)
        peer_update_thread.start()
        
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
            if self.upload_server:
                self.upload_server.close()
                self.upload_server = None
            self.contact_tracker("stopped")

    def pause(self):
        self.paused = True
        self.state = 'paused'

    def resume(self):
        self.paused = False
        if self.piece_manager.all_pieces_downloaded():
            self.state = 'seeding'
        else:
            self.state = 'downloading'

    def stop(self):
        self.running = False
        self.paused = False
        self.state = 'stopped'
        self.contact_tracker("stopped")
        if self.upload_server:
            self.upload_server.close()
            self.upload_server = None
        for peer in self.active_connections[:]:
            try:
                peer.close()
            except:
                pass
        self.active_connections.clear()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LikeTorrent Client")
    parser.add_argument("torrent_file", help="Path to .torrent file")
    parser.add_argument("--base_path", default=os.path.expanduser("../downloads"), help="Directory to download to or seed from")
    parser.add_argument("--download", action="store_true", help="Download the torrent")
    parser.add_argument("--no-seed", action="store_true", help="Do not seed after downloading")
    parser.add_argument("--port", type=int, default=PEER_PORT, help="Port to listen on")
    args = parser.parse_args()
    
    client = Client(args.torrent_file, args.base_path, args.port)
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