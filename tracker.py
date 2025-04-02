# File: tracker.py
import socket
import json
import threading
from config import TRACKER_PORT

class Tracker:
    def __init__(self):
        self.peers = {}  # {torrent_hash: [{"peer_id": str, "ip": str, "port": int}]}
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(('0.0.0.0', TRACKER_PORT))
        self.server.listen(5)
        print(f"Tracker running on port {TRACKER_PORT}")

    def handle_client(self, conn, addr):
        data = conn.recv(1024).decode()
        request = json.loads(data)
        torrent_hash = request["torrent_hash"]
        peer_info = {"peer_id": request["peer_id"], "ip": addr[0], "port": request["port"]}

        if torrent_hash not in self.peers:
            self.peers[torrent_hash] = []
        if peer_info not in self.peers[torrent_hash]:  # Avoid duplicates
            self.peers[torrent_hash].append(peer_info)

        response = {
            "peers": self.peers[torrent_hash]
        }
        conn.send(json.dumps(response).encode())
        conn.close()

    def run(self):
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    tracker = Tracker()
    tracker.run()