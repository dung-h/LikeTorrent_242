# File: ui.py
import sys
import time
import threading
from client import TorrentClient

def main():
    if len(sys.argv) < 2:
        print("Usage: python ui.py <torrent_file>")
        return
    torrent_file = sys.argv[1]
    # client = TorrentClient(torrent_file)
    client = TorrentClient(torrent_file)
    client.port = 6882  # Force a different port from the seeder
    print(f"Client is running on {client.port}")
    print(f"Starting client with torrent: {torrent_file}")
    threading.Thread(target=client.start_upload).start()
    client.start_download()
    while not client.piece_manager.all_pieces_downloaded():
        print(f"Progress: {sum(client.piece_manager.have_pieces)}/{client.piece_manager.total_pieces} pieces")
        time.sleep(1)
    print("Download complete!")

if __name__ == "__main__":
    import time, threading
    main()