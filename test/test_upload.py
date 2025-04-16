import unittest
import threading
import time
import os
import socket
from src.peer.client import TorrentClient
from src.peer.metainfo import Metainfo
import sqlite3

class TestUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create test file and torrent
        with open('upload_test.txt', 'wb') as f:
            f.write(b'Upload data' * 1000)
        meta = Metainfo('upload_test.txt', 'http://localhost:8000')
        meta.save('upload_test.torrent')
        
        # Create the client
        cls.client = TorrentClient('upload_test.torrent', is_seeder=True)
        cls.client.piece_manager.have_pieces = [True] * cls.client.piece_manager.total_pieces
        
        # IMPORTANT: Copy the file to the downloads directory
        import shutil
        os.makedirs(cls.client.piece_manager.download_dir, exist_ok=True)
        shutil.copy('upload_test.txt', os.path.join(cls.client.piece_manager.download_dir, 'upload_test.txt'))
        
        # Start upload thread
        cls.upload_thread = threading.Thread(target=cls.client.start_upload)
        cls.upload_thread.daemon = True
        cls.upload_thread.start()
        time.sleep(1)

    def test_upload(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', self.client.port))
        sock.send(f"ESTABLISH:test_peer".encode())
        self.assertEqual(sock.recv(1024).decode(), "ESTABLISHED")
        sock.send(f"REQUEST:0".encode())
        data = b''
        while len(data) < 512*1024:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        self.assertTrue(len(data) > 0)
        sock.close()
        conn = sqlite3.connect('torrent.db')
        c = conn.cursor()
        c.execute('SELECT bytes_transferred FROM peer_interactions WHERE source_peer_id = ?', (self.client.peer_id,))
        result = c.fetchone()
        self.assertTrue(result[0] > 0)
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.client.stop()
        os.remove('upload_test.txt')
        os.remove('upload_test.torrent')

    
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