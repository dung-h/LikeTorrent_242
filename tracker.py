# # File: tracker.py
# import socket
# import json
# import threading
# from config import TRACKER_PORT

# class Tracker:
#     def __init__(self):
#         self.peers = {}  # {torrent_hash: [{"peer_id": str, "ip": str, "port": int}]}
#         self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         self.server.bind(('0.0.0.0', TRACKER_PORT))
#         self.server.listen(5)
#         print(f"Tracker running on port {TRACKER_PORT}")

#     def handle_client(self, conn, addr):
#         data = conn.recv(1024).decode()
#         request = json.loads(data)
#         torrent_hash = request["torrent_hash"]
#         peer_info = {"peer_id": request["peer_id"], "ip": addr[0], "port": request["port"]}

#         if torrent_hash not in self.peers:
#             self.peers[torrent_hash] = []
#         if peer_info not in self.peers[torrent_hash]:  # Avoid duplicates
#             self.peers[torrent_hash].append(peer_info)

#         response = {
#             "peers": self.peers[torrent_hash]
#         }
#         conn.send(json.dumps(response).encode())
#         conn.close()

#     def run(self):
#         while True:
#             conn, addr = self.server.accept()
#             threading.Thread(target=self.handle_client, args=(conn, addr)).start()

# if __name__ == "__main__":
#     tracker = Tracker()
#     tracker.run()
# File: tracker.py
# File: tracker.py
# File: tracker.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from config import TRACKER_PORT

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
peers = {}  # {torrent_hash: [{"peer_id": str, "ip": str, "port": int}]}

@app.route('/')
def home():
    return "Tracker is running!"

@app.route('/announce', methods=['GET', 'POST'])
def announce():
    print(f"Received {request.method} request to /announce")
    print(f"Request args: {request.args}")
    print(f"Request form: {request.form}")
    try:
        if request.method == 'GET':
            # Get data from URL parameters
            torrent_hash = request.args.get('torrent_hash')
            peer_id = request.args.get('peer_id')
            port = request.args.get('port', type=int)
            downloaded = request.args.get('downloaded', type=int)
            print(f"GET request with: {torrent_hash}, {peer_id}, {port}")
        else:  # POST
            # Get data from JSON body
            data = request.get_json()
            if not data:
                # Try form data if JSON fails
                data = request.form
            torrent_hash = data.get('torrent_hash')
            peer_id = data.get('peer_id')
            port = int(data.get('port', 0))
            downloaded = int(data.get('downloaded', 0))
            print(f"POST request with: {torrent_hash}, {peer_id}, {port}")
            
        # Common processing code
        if not torrent_hash or not peer_id or not port:
            return jsonify({"error": "Missing required parameters"}), 400
            
        peer_info = {"peer_id": peer_id, "ip": request.remote_addr, "port": port}
        
        if torrent_hash not in peers:
            peers[torrent_hash] = []
        if peer_info not in peers[torrent_hash]:  # Avoid duplicates
            peers[torrent_hash].append(peer_info)
            
        return jsonify({"peers": peers[torrent_hash]})
    except Exception as e:
        print(f"Error handling announce request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print(f"HTTP Tracker running on port {TRACKER_PORT}")
    app.run(host='0.0.0.0', port=TRACKER_PORT, debug=True)