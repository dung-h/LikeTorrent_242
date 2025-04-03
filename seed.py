# File: seed.py
import sys
import time
import threading
import os
from client import TorrentClient

def main():
    if len(sys.argv) < 2:
        print("Usage: python seed.py <torrent_file>")
        return

    torrent_file = sys.argv[1]
    client = TorrentClient(torrent_file)
    client.piece_manager.have_pieces = [True] * client.piece_manager.total_pieces  # Mark all pieces as available
    # Use a fixed port for seeder to avoid conflicts
    client.port = 6881
    print(f"Seeder running on port {client.port}")
    
    print(f"Seeding torrent: {torrent_file}")
    
    # Check if the original file exists
    file_path = client.metainfo["files"][0]["path"]
    if not os.path.exists(file_path):
        print(f"Error: Source file '{file_path}' does not exist. Cannot seed.")
        return
    
    file_size = os.path.getsize(file_path)
    print(f"Seeding file: {file_path} ({file_size} bytes)")
    print(f"Seeding... {len(client.metainfo['pieces'])} pieces available")
    
    # First, announce to the tracker that we're seeding
    print("Registering with tracker...")
    client.contact_tracker()
    
    # Start the upload server in a thread
    upload_thread = threading.Thread(target=client.start_upload)
    upload_thread.daemon = True
    upload_thread.start()
    
    print("Seeder is running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(30)
            # Re-announce periodically
            client.contact_tracker()
    except KeyboardInterrupt:
        print("Stopping seeder...")
        client.stop()

if __name__ == "__main__":
    main()