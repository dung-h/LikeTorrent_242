# File: test_torrent.py
import os
import shutil
import subprocess
import threading
import time
import hashlib
import json
import sqlite3
from pathlib import Path

# Project directory
BASE_DIR = r"C:\Users\HAD\OneDrive\Computer\Networking\LikeTorrent"
TORRENT_FILE = "testing.torrent"
VIDEO_FILE = "testing.mp4"
TRACKER_PORT = 8000
PEER_PORTS = {
    "seeder1": 6881,
    "seeder2": 6882,
    "leecher1": 6883,
    "leecher2": 6884,
    "leecher3": 6885,
}
TEST_DIR = os.path.join(BASE_DIR, "test_peers")
CLIENT_FILES = ["client.py", "config.py", "peer.py", "piece_manager.py", "metainfo.py"]

def check_prerequisites():
    """Verify required files and ports."""
    video_path = os.path.join(BASE_DIR, "downloads", VIDEO_FILE)
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"{video_path} not found")
    for file in CLIENT_FILES:
        if not os.path.exists(os.path.join(BASE_DIR, file)):
            raise FileNotFoundError(f"{file} not found")
    # Check port availability
    for port in list(PEER_PORTS.values()) + [TRACKER_PORT]:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("localhost", port))
        except:
            raise RuntimeError(f"Port {port} is already in use")
        finally:
            s.close()

def calculate_file_hash(file_path):
    """Calculate SHA-1 hash of a file."""
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
    return sha1.hexdigest()

def generate_torrent():
    """Generate testing.torrent for testing.mp4."""
    video_path = os.path.join(BASE_DIR, "downloads", VIDEO_FILE)
    torrent_path = os.path.join(BASE_DIR, TORRENT_FILE)
    cmd = [
        "python", "metainfo.py",
        video_path,
        f"http://localhost:{TRACKER_PORT}",
        torrent_path
    ]
    print(f"Generating {TORRENT_FILE}...")
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Torrent generation failed: {result.stderr}")
    print(f"Generated {TORRENT_FILE}")

def setup_peer(peer_name, port, is_seeder):
    """Set up a peer's working directory with client files."""
    peer_dir = os.path.join(TEST_DIR, peer_name)
    os.makedirs(peer_dir, exist_ok=True)
    
    # Copy client files
    for file in CLIENT_FILES:
        src = os.path.join(BASE_DIR, file)
        dst = os.path.join(peer_dir, file)
        shutil.copy(src, dst)
    
    # Copy torrent file
    shutil.copy(os.path.join(BASE_DIR, TORRENT_FILE), peer_dir)
    
    # Handle downloads directory
    downloads_dir = os.path.join(peer_dir, "downloads")
    if is_seeder:
        os.makedirs(downloads_dir, exist_ok=True)
        shutil.copy(os.path.join(BASE_DIR, "downloads", VIDEO_FILE), downloads_dir)
    else:
        if os.path.exists(downloads_dir):
            shutil.rmtree(downloads_dir)
    
    return peer_dir

def run_tracker():
    """Run tracker.py in a thread."""
    cmd = ["python", "tracker.py"]
    print("Starting tracker...")
    process = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(2)  # Wait for tracker to start
    print("Tracker started")
    return process

def run_peer(peer_name, port, peer_dir, is_seeder):
    """Run a peer (seeder or leecher) in a thread."""
    cmd = [
        "python", "client.py",
        TORRENT_FILE,
        "--port", str(port)
    ]
    if is_seeder:
        pass
    else:
        cmd.append("--download")
    
    print(f"Starting {peer_name} on port {port} (seeder: {is_seeder})")
    process = subprocess.Popen(
        cmd,
        cwd=peer_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Monitor output
    start_time = time.time()
    timeout = 900  # 15 minutes
    while process.poll() is None and time.time() - start_time < timeout:
        stdout = process.stdout.readline().strip()
        stderr = process.stderr.readline().strip()
        if stdout:
            print(f"[{peer_name}] {stdout}")
        if stderr:
            print(f"[{peer_name} ERROR] {stderr}")
        time.sleep(0.1)
    
    if process.poll() is None:
        print(f"[{peer_name}] Timed out, terminating")
        process.terminate()
    
    return process

def verify_downloads():
    """Verify that leechers downloaded testing.mp4 correctly."""
    original_file = os.path.join(BASE_DIR, "downloads", VIDEO_FILE)
    original_hash = calculate_file_hash(original_file)
    original_size = os.path.getsize(original_file)
    
    results = {}
    for peer_name, port in PEER_PORTS.items():
        if "leecher" not in peer_name:
            continue
        peer_dir = os.path.join(TEST_DIR, peer_name)
        downloaded_file = os.path.join(peer_dir, "downloads", VIDEO_FILE)
        if os.path.exists(downloaded_file):
            downloaded_hash = calculate_file_hash(downloaded_file)
            downloaded_size = os.path.getsize(downloaded_file)
            success = (downloaded_hash == original_hash and downloaded_size == original_size)
            results[peer_name] = {
                "file_exists": True,
                "hash_match": downloaded_hash == original_hash,
                "size_match": downloaded_size == original_size,
                "success": success
            }
            print(f"[{peer_name}] Download {'successful' if success else 'failed'}: "
                  f"Size={downloaded_size}/{original_size}, Hash={'match' if downloaded_hash == original_hash else 'mismatch'}")
        else:
            results[peer_name] = {
                "file_exists": False,
                "hash_match": False,
                "size_match": False,
                "success": False
            }
            print(f"[{peer_name}] Download failed: File not found")
    
    return results

def main():
    try:
        # Check prerequisites
        check_prerequisites()
        
        # Clean up previous test directory and database
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
        db_path = os.path.join(BASE_DIR, "torrent.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        
        # Generate torrent file
        generate_torrent()
        
        # Set up peer directories
        peer_dirs = {}
        for peer_name, port in PEER_PORTS.items():
            is_seeder = "seeder" in peer_name
            peer_dirs[peer_name] = setup_peer(peer_name, port, is_seeder)
        
        # Start tracker
        tracker_process = run_tracker()
        
        # Start peers in threads
        peer_threads = []
        peer_processes = {}
        for peer_name, port in PEER_PORTS.items():
            is_seeder = "seeder" in peer_name
            thread = threading.Thread(
                target=lambda: peer_processes.update({peer_name: run_peer(peer_name, port, peer_dirs[peer_name], is_seeder)})
            )
            peer_threads.append(thread)
            thread.start()
        
        # Wait for peers to complete or timeout
        for thread in peer_threads:
            thread.join(timeout=900)
        
        # Terminate all processes
        tracker_process.terminate()
        for peer_name, process in peer_processes.items():
            process.terminate()
        
        # Verify downloads
        results = verify_downloads()
        
        # Print summary
        print("\nTest Summary:")
        successful = sum(1 for r in results.values() if r["success"])
        total_leechers = len([k for k in PEER_PORTS if 'leecher' in k])
        print(f"Leechers successful: {successful}/{total_leechers}")
        if successful == total_leechers:
            print("Test PASSED: All leechers downloaded testing.mp4 correctly")
        else:
            print("Test FAILED: Some leechers did not download correctly")
    
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Clean up
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
        print("Cleaned up test directories")

if __name__ == "__main__":
    main()