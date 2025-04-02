# File: seed.py
import sys
import time
import threading
from client import TorrentClient

def main():
    if len(sys.argv) < 2:
        print("Usage: python seed.py <torrent_file>")
        return

    torrent_file = sys.argv[1]
    client = TorrentClient(torrent_file)
    print(f"Seeding torrent: {torrent_file}")
    
    # Check if the original file exists
    file_path = client.metainfo["files"][0]["path"]
    if not os.path.exists(file_path):
        print(f"Error: Source file '{file_path}' does not exist. Cannot seed.")
        return
        
    print(f"Seeding file: {file_path}")
    print(f"Seeding... {len(client.metainfo['pieces'])} pieces available")
    
    # Start the upload server and keep it running
    client.start_upload()  # This will block until interrupted

if __name__ == "__main__":
    import os  # Add this import
    main()