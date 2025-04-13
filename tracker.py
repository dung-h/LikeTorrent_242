# File: tracker.py
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from config import TRACKER_PORT

app = Flask(__name__)
CORS(app)

def init_db():
    conn = sqlite3.connect('torrent.db')
    c = conn.cursor()
    # Replace with this:
    c.execute('''CREATE TABLE IF NOT EXISTS torrents (
        hash TEXT PRIMARY KEY,
        name TEXT,
        piece_length INTEGER,
        total_pieces INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        torrent_hash TEXT NOT NULL,
        path TEXT NOT NULL,
        length INTEGER NOT NULL,
        start_offset INTEGER NOT NULL, -- For multi-file torrents
        FOREIGN KEY (torrent_hash) REFERENCES torrents(hash)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS peers (
        peer_id TEXT PRIMARY KEY,
        ip TEXT,
        port INTEGER,
        state TEXT,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create peer_torrents table
    c.execute('''CREATE TABLE IF NOT EXISTS peer_torrents (
        peer_id TEXT,
        torrent_hash TEXT,
        pieces_owned TEXT,
        downloaded_bytes INTEGER DEFAULT 0,
        state TEXT,
        PRIMARY KEY (peer_id, torrent_hash),
        FOREIGN KEY (peer_id) REFERENCES peers(peer_id),
        FOREIGN KEY (torrent_hash) REFERENCES torrents(hash)
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
        FOREIGN KEY (target_peer_id) REFERENCES peers(peer_id),
        FOREIGN KEY (torrent_hash) REFERENCES torrents(hash)
    )''')
    conn.commit()
    conn.close()

@app.route('/announce', methods=['GET', 'POST'])
def announce():
    try:
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        data = request.args if request.method == 'GET' else (request.get_json() or request.form)
        torrent_hash = data.get('torrent_hash')
        peer_id = data.get('peer_id')
        port = int(data.get('port', 0))
        downloaded = int(data.get('downloaded', 0))
        event = data.get('event', 'started')

        if not all([torrent_hash, peer_id, port]):
            return jsonify({"error": "Missing parameters"}), 400

        conn = sqlite3.connect('torrent.db')
        c = conn.cursor()

        # Update or insert peer
        c.execute('''INSERT OR REPLACE INTO peers (peer_id, ip, port, state, last_seen)
                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                  (peer_id, client_ip, port, 'active' if event != 'stopped' else 'stopped'))

        # Ensure torrent exists
        c.execute('SELECT total_pieces FROM torrents WHERE hash = ?', (torrent_hash,))
        torrent = c.fetchone()
        if not torrent:
            # Assume default piece_length for new torrents; ideally provided by client
            c.execute('''INSERT INTO torrents (hash, name, piece_length, total_pieces)
                         VALUES (?, ?, ?, ?)''',
                      (torrent_hash, request.host_url, 512*1024, 1))  # Placeholder total_pieces

        # Update peer_torrents
        c.execute('SELECT pieces_owned FROM peer_torrents WHERE peer_id = ? AND torrent_hash = ?',
                  (peer_id, torrent_hash))
        existing = c.fetchone()
        pieces_owned = existing[0] if existing else json.dumps([False] * (torrent[0] if torrent else 1))
        state = {'started': 'downloading', 'completed': 'seeding', 'stopped': 'stopped'}.get(event, 'downloading')
        c.execute('''INSERT OR REPLACE INTO peer_torrents (peer_id, torrent_hash, pieces_owned, downloaded_bytes, state)
                     VALUES (?, ?, ?, ?, ?)''',
                  (peer_id, torrent_hash, pieces_owned, downloaded, state))

        # Get peers
        c.execute('''SELECT p.peer_id, p.ip, p.port FROM peers p
             JOIN peer_torrents pt ON p.peer_id = pt.peer_id
             WHERE pt.torrent_hash = ? AND p.state = 'active' AND p.peer_id != ?''',
          (torrent_hash, peer_id))
        peers = [{"peer_id": row[0], "ip": row[1], "port": row[2]} for row in c.fetchall()]

        conn.commit()
        conn.close()
        return jsonify({"peers": peers})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/scrape', methods=['GET'])
def scrape():
    conn = sqlite3.connect('torrent.db')
    c = conn.cursor()
    torrent_hash = request.args.get('torrent_hash')
    if not torrent_hash:
        conn.close()
        return jsonify({"error": "Missing torrent_hash"}), 400
    c.execute('''SELECT state FROM peer_torrents WHERE torrent_hash = ?''', (torrent_hash,))
    states = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({
        "complete": states.count('seeding'),
        "downloaded": len(states),
        "incomplete": states.count('downloading')
    })

if __name__ == "__main__":
    init_db()
    print(f"HTTP Tracker running on port {TRACKER_PORT}")
    app.run(host='0.0.0.0', port=TRACKER_PORT, debug=True)