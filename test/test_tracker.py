import unittest
import threading
import time
import requests
import sqlite3
from src.tracker.tracker import app, init_db

class TestTracker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        app.config['TESTING'] = True
        cls.client = app.test_client()
        cls.tracker_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 8000})
        cls.tracker_thread.daemon = True
        cls.tracker_thread.start()
        time.sleep(1)  # Wait for server to start

    def test_announce(self):
        response = requests.get('http://localhost:8000/announce', params={
            'torrent_hash': 'test_hash',
            'peer_id': 'peer1',
            'port': 6881,
            'downloaded': 0,
            'event': 'started'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('peers', data)
        self.assertTrue(isinstance(data['peers'], list))

        # Verify database
        conn = sqlite3.connect('torrent.db')
        c = conn.cursor()
        c.execute('SELECT peer_id, state FROM peers WHERE peer_id = ?', ('peer1',))
        result = c.fetchone()
        conn.close()
        self.assertEqual(result, ('peer1', 'active'))

    def test_scrape(self):
        # Add a peer first
        requests.get('http://localhost:8000/announce', params={
            'torrent_hash': 'test_hash',
            'peer_id': 'peer2',
            'port': 6882,
            'downloaded': 512000,
            'event': 'completed'
        })
        response = requests.get('http://localhost:8000/scrape', params={'torrent_hash': 'test_hash'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('complete', data)
        self.assertEqual(data['complete'], 1)
        self.assertEqual(data['incomplete'], 1)  # Includes peer1 from test_announce

    @classmethod
    def tearDownClass(cls):
        conn = sqlite3.connect('torrent.db')
        c = conn.cursor()
        c.execute('DELETE FROM peers')
        c.execute('DELETE FROM peer_torrents')
        c.execute('DELETE FROM torrents')
        conn.commit()
        conn.close()
    # Add to all test files
    def setUp(self):
    # Connect to test database
        self.test_db = sqlite3.connect('test_torrent.db', timeout=30)
        c = self.test_db.cursor()
        
        # Create necessary tables
        c.execute('''CREATE TABLE IF NOT EXISTS torrents (
            hash TEXT PRIMARY KEY,
            name TEXT, 
            piece_length INTEGER,
            total_pieces INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS peers (
            peer_id TEXT PRIMARY KEY,
            ip TEXT NOT NULL, 
            port INTEGER NOT NULL,
            state TEXT NOT NULL,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS peer_torrents (
            peer_id TEXT,
            torrent_hash TEXT, 
            pieces_owned TEXT,
            downloaded_bytes INTEGER DEFAULT 0,
            state TEXT,
            PRIMARY KEY (peer_id, torrent_hash)
        )''')
        self.test_db.commit()
        
    def tearDown(self):
    # Clean up test data AND close connections
        try:
            c = self.test_db.cursor()
            c.execute('DELETE FROM peers')
            c.execute('DELETE FROM peer_torrents')
            c.execute('DELETE FROM torrents')
            self.test_db.commit()
        except Exception as e:
            print(f"Cleanup error: {e}")
        finally:
            if hasattr(self, 'test_db'):
                self.test_db.close()

if __name__ == '__main__':
    unittest.main()