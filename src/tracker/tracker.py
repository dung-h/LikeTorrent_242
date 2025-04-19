# File: src/tracker/tracker.py
import threading
import logging
import time
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Tracker:
    def __init__(self, db_path="torrent.db"):
        self.app = Flask(__name__)
        CORS(self.app)
        self.db_path = db_path
        self.announce_count = 0
        self.lock = threading.Lock()
        self.setup_database()
        self.setup_routes()

        # In tracker.py, modify the database setup
    def setup_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS torrents (
                    torrent_hash TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_downloaded BIGINT DEFAULT 0,
                    total_uploaded BIGINT DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS peers (
                    peer_id TEXT,
                    torrent_hash TEXT,
                    ip TEXT,
                    port INTEGER,
                    event TEXT,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    downloaded BIGINT DEFAULT 0,
                    uploaded BIGINT DEFAULT 0,
                    download_rate FLOAT DEFAULT 0,
                    upload_rate FLOAT DEFAULT 0,
                    PRIMARY KEY (peer_id, torrent_hash),
                    FOREIGN KEY (torrent_hash) REFERENCES torrents(torrent_hash)
                )
            """)
            conn.commit()
        logging.info("Database initialized")

    def setup_routes(self):
        @self.app.route('/announce', methods=['GET'])
        def announce():
            try:
                peer_id = request.args.get('peer_id')
                torrent_hash = request.args.get('torrent_hash')
                port = request.args.get('port')
                event = request.args.get('event', '')
                ip = request.remote_addr
                
                # Get download/upload statistics
                downloaded = int(request.args.get('downloaded', 0))
                uploaded = int(request.args.get('uploaded', 0))
                download_rate = float(request.args.get('download_rate', 0))
                upload_rate = float(request.args.get('upload_rate', 0))
        
                logging.info(f"Announce: peer_id={peer_id}, torrent_hash={torrent_hash}, ip={ip}, port={port}, "
                            f"event={event}, down_rate={download_rate:.2f}, up_rate={upload_rate:.2f}")
        
                with self.lock:
                    self.announce_count += 1
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        # Insert torrent if not exists
                        cursor.execute("INSERT OR IGNORE INTO torrents (torrent_hash) VALUES (?)", (torrent_hash,))
                        
                        if event == 'stopped':
                            cursor.execute("DELETE FROM peers WHERE peer_id = ? AND torrent_hash = ?", (peer_id, torrent_hash))
                        else:
                            # Update peer with rate information
                            cursor.execute("""
                                INSERT OR REPLACE INTO peers 
                                (peer_id, torrent_hash, ip, port, event, last_seen, downloaded, uploaded, download_rate, upload_rate)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (peer_id, torrent_hash, ip, int(port) if port.isdigit() else 0, event, time.time(),
                                  downloaded, uploaded, download_rate, upload_rate))
                            
                            # Update torrent totals
                            if event == 'completed' or event == 'started':
                                cursor.execute("""
                                    UPDATE torrents SET 
                                    total_downloaded = total_downloaded + ?,
                                    total_uploaded = total_uploaded + ?
                                    WHERE torrent_hash = ?
                                """, (downloaded, uploaded, torrent_hash))
                        
                        # Get peers for this torrent with additional information
                        cursor.execute("""
                            SELECT peer_id, ip, port, event, downloaded, uploaded, download_rate, upload_rate
                            FROM peers WHERE torrent_hash = ?
                        """, (torrent_hash,))
                        
                        peers = [{
                            "peer_id": row[0], 
                            "ip": row[1], 
                            "port": row[2], 
                            "event": row[3],
                            "downloaded": row[4],
                            "uploaded": row[5],
                            "download_rate": row[6],
                            "upload_rate": row[7]
                        } for row in cursor.fetchall()]
                        
                        conn.commit()
        
                    response = {'peers': peers}
                    return jsonify(response), 200
            except Exception as e:
                logging.error(f"Announce error: {e}")
                return jsonify({'error': str(e)}), 500
        @self.app.route('/scrape', methods=['GET'])

        def scrape():
            try:
                torrent_hash = request.args.get('torrent_hash')
                with self.lock:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT event FROM peers WHERE torrent_hash = ?", (torrent_hash,))
                        rows = cursor.fetchall()
                        if rows:
                            complete = sum(1 for row in rows if row[0] == 'completed')
                            incomplete = len(rows) - complete
                            return jsonify({
                                'complete': complete,
                                'incomplete': incomplete,
                                'peers': len(rows)
                            }), 200
                        return jsonify({'error': 'Torrent not found'}), 404
            except Exception as e:
                logging.error(f"Scrape error: {e}")
                return jsonify({'error': str(e)}), 500

    def cleanup_peers(self):
        while True:
            try:
                with self.lock:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM peers WHERE last_seen < ?", (time.time() - 3600,))
                        cursor.execute("DELETE FROM torrents WHERE NOT EXISTS (SELECT 1 FROM peers WHERE peers.torrent_hash = torrents.torrent_hash)")
                        conn.commit()
                        logging.debug("Cleaned up stale peers")
            except Exception as e:
                logging.error(f"Cleanup error: {e}")
            time.sleep(300)

    def get_torrents(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT torrent_hash, total_downloaded, total_uploaded FROM torrents")
            torrents = {row[0]: {
                "total_downloaded": row[1],
                "total_uploaded": row[2],
                "peers": {}
            } for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT torrent_hash, peer_id, ip, port, event, last_seen, 
                       downloaded, uploaded, download_rate, upload_rate 
                FROM peers
            """)
            
            for row in cursor.fetchall():
                torrent_hash = row[0]
                peer_id = row[1]
                torrents[torrent_hash]["peers"][peer_id] = {
                    'peer_id': peer_id,
                    'ip': row[2],
                    'port': row[3],
                    'event': row[4],
                    'last_seen': row[5],
                    'downloaded': row[6],
                    'uploaded': row[7],
                    'download_rate': row[8],
                    'upload_rate': row[9]
                }
            return torrents

    def run(self, host='0.0.0.0', port=8000):
        threading.Thread(target=self.cleanup_peers, daemon=True).start()
        logging.info(f"Starting tracker on {host}:{port}")
        self.app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    tracker = Tracker()
    tracker.run()