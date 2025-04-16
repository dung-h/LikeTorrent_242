import unittest
import tkinter as tk
from src.ui import TorrentGUI
import os
from src.peer.metainfo import Metainfo
import sqlite3

class TestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open('ui_test.txt', 'w') as f:
            f.write('UI test data')
        meta = Metainfo('ui_test.txt', 'http://localhost:8000')
        meta.save('ui_test.torrent')

    def test_gui_load(self):
        root = tk.Tk()
        app = TorrentGUI(root)
        app.torrent_entry.insert(0, 'ui_test.torrent')
        app.dir_entry.insert(0, 'downloads')
        app.start_client()
        self.assertIsNotNone(app.client)
        root.destroy()

    @classmethod
    def tearDownClass(cls):
        os.remove('ui_test.txt')
        os.remove('ui_test.torrent')
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