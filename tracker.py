# File: tracker.py
import json
import sqlite3
import time
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)
TRACKER_PORT = 8000

def init_db():
    conn = sqlite3.connect('torrent.db', timeout=10)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS peers (
                    peer_id TEXT PRIMARY KEY,
                    ip TEXT,
                    port INTEGER,
                    state TEXT,
                    last_seen TIMESTAMP
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS torrents (
                    hash TEXT PRIMARY KEY,
                    name TEXT,
                    piece_length INTEGER,
                    total_pieces INTEGER
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS peer_torrents (
                    peer_id TEXT,
                    torrent_hash TEXT,
                    pieces_owned TEXT,
                    downloaded_bytes INTEGER,
                    state TEXT,
                    PRIMARY KEY (peer_id, torrent_hash),
                    FOREIGN KEY (peer_id) REFERENCES peers(peer_id)
                 )''')
    conn.commit()
    conn.close()
    print("Initialized database tables")

def cleanup_peers():
    while True:
        try:
            conn = sqlite3.connect('torrent.db', timeout=10)
            c = conn.cursor()
            c.execute("DELETE FROM peers WHERE last_seen < datetime('now', '-5 minutes') AND state != 'active'")
            deleted = c.rowcount
            if deleted > 0:
                print(f"Cleaned up {deleted} stale peers")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(300)

@app.route('/announce', methods=['GET'])
def announce():
    try:
        peer_id = request.args.get('peer_id')
        torrent_hash = request.args.get('torrent_hash')
        port = int(request.args.get('port'))
        event = request.args.get('event', 'started')
        client_ip = request.remote_addr

        conn = sqlite3.connect('torrent.db', timeout=10)
        c = conn.cursor()

        c.execute("DELETE FROM peers WHERE last_seen < datetime('now', '-5 minutes') AND state != 'active'")
        if event != 'stopped':
            c.execute('''INSERT OR REPLACE INTO peers (peer_id, ip, port, state, last_seen)
                         VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                      (peer_id, client_ip, port, 'active'))
            c.execute('''INSERT OR IGNORE INTO torrents (hash, name, piece_length, total_pieces)
                         VALUES (?, ?, ?, ?)''',
                      (torrent_hash, "unknown", 524288, 0))
            c.execute('''INSERT OR REPLACE INTO peer_torrents (peer_id, torrent_hash, pieces_owned, downloaded_bytes, state)
                         VALUES (?, ?, ?, ?, ?)''',
                      (peer_id, torrent_hash, json.dumps([]), 0, 'active'))
        else:
            c.execute('UPDATE peers SET state = ? WHERE peer_id = ?', ('stopped', peer_id))
        conn.commit()

        c.execute('SELECT ip, port, peer_id FROM peers WHERE state = ? AND peer_id != ?', ('active', peer_id))
        peers = [{'ip': row[0], 'port': row[1], 'peer_id': row[2]} for row in c.fetchall()]
        conn.close()

        print(f"Returning peers to {peer_id}: {peers}")
        return jsonify({"peers": peers})
    except Exception as e:
        print(f"Announce error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    init_db()
    print(f"HTTP Tracker running on port {TRACKER_PORT}")
    threading.Thread(target=cleanup_peers, daemon=True).start()
    app.run(host='0.0.0.0', port=TRACKER_PORT, debug=False)