import unittest
import requests
import sqlite3

class TestScrape(unittest.TestCase):
    def test_scrape_endpoint(self):
        # Add peers
        requests.get('http://localhost:8000/announce', params={
            'torrent_hash': 'scrape_test',
            'peer_id': 'peer3',
            'port': 6883,
            'downloaded': 0,
            'event': 'started'
        })
        requests.get('http://localhost:8000/announce', params={
            'torrent_hash': 'scrape_test',
            'peer_id': 'peer4',
            'port': 6884,
            'downloaded': 512000,
            'event': 'completed'
        })
        response = requests.get('http://localhost:8000/scrape', params={'torrent_hash': 'scrape_test'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['complete'], 1)
        self.assertEqual(data['incomplete'], 1)
        self.assertEqual(data['downloaded'], 2)

    def tearDown(self):
        conn = sqlite3.connect('torrent.db')
        c = conn.cursor()
        c.execute('DELETE FROM peers WHERE peer_id IN (?, ?)', ('peer3', 'peer4'))
        c.execute('DELETE FROM peer_torrents WHERE torrent_hash = ?', ('scrape_test',))
        c.execute('DELETE FROM torrents WHERE torrent_hash = ?', ('scrape_test',))
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