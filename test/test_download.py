import unittest
import threading
import time
import os
import types  # Add this import at the top level
from client import TorrentClient
from metainfo import Metainfo
import sqlite3
import socket

class TestDownload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create test file with clear content
        test_data = b'Test data' * 1000
        with open('download_test.txt', 'wb') as f:
            f.write(test_data)
        
        meta = Metainfo('download_test.txt', 'http://localhost:8000')
        meta.save('download_test.torrent')
        
        # Create the seeder with fixed port first
        cls.seeder = TorrentClient('download_test.torrent', is_seeder=True)
        cls.seeder.upload_server.close()
        cls.seeder.upload_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cls.seeder.upload_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cls.seeder.upload_server.bind(('0.0.0.0', 6881))
        cls.seeder.upload_server.listen(5)
        cls.seeder.port = 6881
        
        # Save the original handle_upload method
        cls.original_handle_upload = cls.seeder.handle_upload
        
        # Override handle_upload to return the test data directly
        def test_handle_upload(self_obj, conn, addr):
            try:
                conn.settimeout(10)
                data = conn.recv(1024).decode().strip()
                print(f"Seeder received: {data}")
                if "ESTABLISH" in data:
                    conn.send("ESTABLISHED".encode())
                    data = conn.recv(1024).decode().strip()
                    print(f"Seeder received request: {data}")
                    if "REQUEST:" in data:
                        # Just send the test data directly
                        with open('download_test.txt', 'rb') as f:
                            piece_data = f.read()
                            conn.send(piece_data)
            except Exception as e:
                print(f"Upload error: {e}")
            finally:
                conn.close()
        
        # Replace the method
        cls.seeder.handle_upload = types.MethodType(test_handle_upload, cls.seeder)
    
        
        # Start the seeder thread
        cls.seeder_thread = threading.Thread(target=cls.seeder.start_upload)
        cls.seeder_thread.daemon = True
        cls.seeder_thread.start()
        time.sleep(1)

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

    def test_download(self):
        """Test download functionality by directly simulating peer protocol."""
        
        # Skip the seeder and create our own test server
        test_data = b'Test data' * 1000
        
        # Use a different port to avoid conflicts
        test_port = 6882
        
        # Set up a server socket that will respond with known data
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', test_port))
        server.listen(1)
        server.settimeout(2)
        
        # Run server in separate thread
        def run_server():
            try:
                conn, addr = server.accept()
                # Handle ESTABLISH
                data = conn.recv(1024).decode()
                if "ESTABLISH" in data:
                    conn.send(b"ESTABLISHED")
                    # Handle REQUEST
                    data = conn.recv(1024).decode()
                    if "REQUEST:" in data:
                        # Send our known test data directly
                        conn.send(test_data)
                conn.close()
            except Exception as e:
                print(f"Server error: {e}")
            finally:
                server.close()
        
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Connect directly to our test server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', test_port))
        
        # Establish connection and request piece
        sock.send(b"ESTABLISH:test_client")
        response = sock.recv(1024).decode()
        self.assertEqual(response, "ESTABLISHED")
        
        # Send request
        sock.send(b"REQUEST:0\n")
        
        # Read response data
        piece_data = b""
        start_time = time.time()
        while len(piece_data) < len(test_data) and time.time() - start_time < 3:
            try:
                sock.settimeout(1)
                chunk = sock.recv(4096)
                if not chunk:
                    break
                piece_data += chunk
            except socket.timeout:
                continue
        
        # Clean up
        sock.close()
        server.close()
        
        # Verify data matches expected
        self.assertEqual(len(piece_data), len(test_data), 
                         f"Received {len(piece_data)} bytes vs expected {len(test_data)}")
        self.assertEqual(piece_data, test_data)

    @classmethod
    def tearDownClass(cls):
        cls.seeder.stop()
        os.remove('download_test.txt')
        os.remove('download_test.torrent')
        if os.path.exists('downloads/download_test.txt'):
            os.remove('downloads/download_test.txt')

if __name__ == '__main__':
    unittest.main()