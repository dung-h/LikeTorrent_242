import os
import json
import sqlite3
from config import PIECE_SIZE, DOWNLOAD_DIR

class PieceManager:
    def __init__(self, metainfo, is_seeder=False, db=None, client_peer_id=None):
        self.db = db
        self.metainfo = metainfo
        self.total_pieces = len(metainfo["pieces"])
        self.download_dir = metainfo.get("download_dir", DOWNLOAD_DIR)
        os.makedirs(self.download_dir, exist_ok=True)
        self.files = metainfo["files"]
        self.client_peer_id = client_peer_id
        
        # Initialize piece ownership
        if is_seeder:
            self.have_pieces = [True] * self.total_pieces
        else:
            # For leechers, check if we actually have the complete file
            all_files_complete = True
            for file_info in self.files:
                path = os.path.join(self.download_dir, file_info["path"])
                if not os.path.exists(path) or os.path.getsize(path) != file_info["length"]:
                    all_files_complete = False
                    break
                    
            if all_files_complete:
                # Verify the file content against the piece hashes
                print("Files found, checking if content matches expected hashes...")
                self.have_pieces = [self.verify_existing_piece(i) for i in range(self.total_pieces)]
            else:
                self.have_pieces = [False] * self.total_pieces
                
            print(f"Initialized with {sum(self.have_pieces)}/{self.total_pieces} pieces")
    
        # For leechers, initialize the destination files with correct sizes.
        if not is_seeder:
            for file_info in self.files:
                path = os.path.join(self.download_dir, file_info["path"])
                os.makedirs(os.path.dirname(path), exist_ok=True)
                # Only create/truncate the file if it doesn't exist or has wrong size
                if not os.path.exists(path) or os.path.getsize(path) != file_info["length"]:
                    with open(path, "wb") as f:
                        f.truncate(file_info["length"])
                    

    def verify_existing_piece(self, piece_index):
        """Check if an existing piece on disk matches the expected hash."""
        try:
            expected_len = self.expected_piece_length(piece_index)
            piece_offset = piece_index * self.metainfo["piece_length"]
            piece_data = b''
            
            # Read the piece data from disk
            for file_info in self.files:
                file_path = os.path.join(self.download_dir, file_info["path"])
                file_start = file_info.get("start_offset", 0)
                file_end = file_start + file_info["length"]
                
                if file_end <= piece_offset:
                    continue
                    
                if file_start >= piece_offset + expected_len:
                    break
                    
                # Calculate overlap
                overlap_start = max(piece_offset, file_start)
                overlap_end = min(piece_offset + expected_len, file_end)
                overlap_length = overlap_end - overlap_start
                
                if overlap_length <= 0:
                    continue
                    
                # Calculate file offset
                file_offset = overlap_start - file_start
                
                # Calculate piece data offset
                piece_data_offset = overlap_start - piece_offset
                
                # Read the relevant part of the file
                with open(file_path, "rb") as f:
                    f.seek(file_offset)
                    data = f.read(overlap_length)
                    
                    # Add the data at the correct offset in the piece buffer
                    if len(piece_data) < piece_data_offset + len(data):
                        piece_data = piece_data.ljust(piece_data_offset, b'\0')
                        piece_data = piece_data[:piece_data_offset] + data
            
            # Verify against expected hash
            import hashlib
            piece_hash = hashlib.sha1(piece_data).hexdigest()
            expected_hash = self.metainfo["pieces"][piece_index]
            
            return piece_hash == expected_hash
        except Exception as e:
            print(f"Error verifying existing piece {piece_index}: {e}")
            return False
        
    def expected_piece_length(self, piece_index):
        """Return the expected length for this piece.
        For the last piece (or only piece in a small file) the length may be smaller."""
        total_file_length = sum(file_info["length"] for file_info in self.files)
        piece_length = self.metainfo["piece_length"]
        if (piece_index + 1) * piece_length > total_file_length:
            return total_file_length - piece_index * piece_length
        return piece_length

    def write_piece(self, piece_index, piece_data):
        """Write a piece to the appropriate file(s) using proper offset calculation."""
        piece_offset = piece_index * self.metainfo["piece_length"]
        expected_len = self.expected_piece_length(piece_index)
        piece_remaining = expected_len
        piece_cursor = 0
        
        # Process each file that might contain part of this piece
        for file_info in self.files:
            file_path = os.path.join(self.download_dir, file_info["path"])
            file_start = file_info.get("start_offset", 0)
            file_end = file_start + file_info["length"]
            
            # Skip files that are completely before this piece
            if file_end <= piece_offset:
                continue
            
            # If this file is completely after the piece, break out
            if file_start >= piece_offset + piece_remaining:
                break
                
            # Calculate overlap between the piece and the file
            overlap_start = max(piece_offset, file_start)
            overlap_end = min(piece_offset + piece_remaining, file_end)
            overlap_length = overlap_end - overlap_start
            
            if overlap_length <= 0:
                continue
                
            # Calculate where to write in the file
            file_offset = overlap_start - file_start
            
            # Calculate which part of piece_data to write
            piece_data_offset = overlap_start - piece_offset
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            # Create file with correct size if it doesn't exist
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    f.truncate(file_info["length"])
            
            # Write the data
            with open(file_path, "r+b") as f:
                f.seek(file_offset)
                f.write(piece_data[piece_data_offset: piece_data_offset + overlap_length])
            
            piece_cursor += overlap_length
            if piece_cursor >= piece_remaining:
                break

    def verify_piece(self, piece_index, piece_data):
        """Verify a piece's hash matches the expected hash."""
        import hashlib
        
        # Calculate hash of received data
        calculated_hash = hashlib.sha1(piece_data).hexdigest()
        
        # Get expected hash from metainfo (ensure comparison of same formats)
        expected_hash = self.metainfo["pieces"][piece_index]
        
        # Debug to see what's happening
        print(f"Expected hash: {expected_hash}")
        print(f"Calculated hash: {calculated_hash}")
        
        return calculated_hash == expected_hash
    def piece_complete(self, piece_index, piece_data):
        """Verify and write a completed piece."""
        if self.verify_piece(piece_index, piece_data):
            if not self.have_pieces[piece_index]:
                self.have_pieces[piece_index] = True
                expected_len = self.expected_piece_length(piece_index)
                trimmed_piece = piece_data[:expected_len]
                self.write_piece(piece_index, trimmed_piece)
                c = self.db.cursor()
                c.execute('UPDATE peer_torrents SET pieces_owned = ?, downloaded_bytes = ? WHERE torrent_hash = ?',
                          (json.dumps(self.have_pieces),
                           sum(self.have_pieces) * self.metainfo["piece_length"],
                           self.metainfo["torrent_hash"]))
                self.db.commit()
            return True
        else:
            print(f"Piece {piece_index} failed verification! Discarding.")
            return False

    def all_pieces_downloaded(self):
        return all(self.have_pieces)

    def missing_pieces(self):
        """Return indices of pieces that still need to be downloaded."""
        print(f"Checking missing pieces. Current status: {self.have_pieces}")
        return [i for i, has_piece in enumerate(self.have_pieces) if not has_piece]