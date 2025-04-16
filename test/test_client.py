import unittest
import os
import sqlite3
from src.peer.metainfo import Metainfo
from src.peer.client import TorrentClient
import hashlib
import json
import threading

class TestClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a test torrent
        with open('test.txt', 'w') as f:
            f.write('Test data')
        meta = Metainfo('test.txt', 'http://localhost:8000')
        meta.save('test.torrent')

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

    # Update test_client_init method
    def test_client_init(self):
        client = TorrentClient('test.torrent')
        self.assertTrue(client.peer_id)
        
        # Open the actual torrent file to get the correct hash
        with open('test.torrent', 'r') as f:
            torrent_data = json.load(f)
            
        self.assertEqual(client.metainfo['torrent_hash'], torrent_data['torrent_hash'])

    # Add this helper function to your test file

    def test_pause_resume(self):
        client = create_test_client('test.torrent')
        
        # Make sure client exists in test DB
        client.update_db_state()  # Now using our patched version
        
        client.pause()
        c = self.test_db.cursor()
        c.execute('SELECT state FROM peers WHERE peer_id = ?', (client.peer_id,))
        self.assertEqual(c.fetchone()[0], 'paused')
        
        client.resume()
        c = self.test_db.cursor()
        c.execute('SELECT state FROM peers WHERE peer_id = ?', (client.peer_id,))
        self.assertEqual(c.fetchone()[0], 'downloading')
        
        client.stop()

    @classmethod
    def tearDownClass(cls):
        os.remove('test.txt')
        os.remove('test.torrent')
        conn = sqlite3.connect('torrent.db')
        c = conn.cursor()
        c.execute('DELETE FROM peers')
        c.execute('DELETE FROM peer_torrents')
        conn.commit()
        conn.close()

# Fix this method by adding self parameter
def create_test_client(torrent_file, is_seeder=False):
    client = TorrentClient(torrent_file, is_seeder=is_seeder)
    # Replace the client's database connection with test-specific one
    client.db.close()  # Close original connection
    client.db = sqlite3.connect('test_torrent.db', timeout=30, check_same_thread=False)
    client.init_db()
    
    # Save the original method
    original_update_db_state = client.update_db_state
    
    # Create a patched version that uses test_torrent.db
    def patched_update_db_state():
        local_db = sqlite3.connect('test_torrent.db')
        with threading.Lock():
            c = local_db.cursor()
            c.execute('''INSERT OR REPLACE INTO peers (peer_id, ip, port, state)
                      VALUES (?, ?, ?, ?)''',
                     (client.peer_id, '127.0.0.1', client.port, client.state))
            pieces_owned = json.dumps(client.piece_manager.have_pieces)
            c.execute('''INSERT OR REPLACE INTO peer_torrents (peer_id, torrent_hash, pieces_owned, downloaded_bytes, state)
                      VALUES (?, ?, ?, ?, ?)''',
                     (client.peer_id, client.metainfo["torrent_hash"], pieces_owned,
                     sum(client.piece_manager.have_pieces) * client.metainfo["piece_length"], client.state))
            local_db.commit()
            local_db.close()
    
    # Replace the method
    client.update_db_state = patched_update_db_state
    
    # Make sure to add the required import
    import threading
    
    return client

if __name__ == '__main__':
    unittest.main()