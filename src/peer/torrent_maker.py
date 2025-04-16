# File: torrent_maker.py
import os
import hashlib
import bencodepy
import math
import logging
from src.peer.config import PIECE_SIZE

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_torrent_file(files, tracker_url, output_path):
    metainfo = {
        "announce": tracker_url,
        "info": {
            "piece_length": int(PIECE_SIZE),  # Ensure integer
            "pieces": bytearray(),  # Initialize as bytearray instead of list
            "name": os.path.basename(files[0]) if len(files) == 1 else os.path.basename(os.path.dirname(files[0]) or "torrent")
        }
    }
    total_length = 0
    file_list = []
    
    for file_path in files:
        file_size = os.path.getsize(file_path)
        total_length += file_size
        file_list.append({
            "length": file_size,
            "path": [os.path.relpath(file_path, os.path.dirname(files[0])).replace("\\", "/")]
        })
    
    if len(files) > 1:
        metainfo["info"]["files"] = file_list
    else:
        metainfo["info"]["length"] = total_length
    
    piece_data = bytearray()
    pieces_hash_bytes = bytearray()  # Store all piece hashes as a continuous byte array
    
    for file_path in files:
        with open(file_path, "rb") as f:
            while chunk := f.read(PIECE_SIZE - len(piece_data)):
                piece_data.extend(chunk)
                if len(piece_data) == PIECE_SIZE:
                    piece_hash = hashlib.sha1(piece_data).digest()
                    pieces_hash_bytes.extend(piece_hash)  # Add hash bytes directly to the bytearray
                    piece_data = bytearray()
    
    if piece_data:
        piece_hash = hashlib.sha1(piece_data).digest()
        pieces_hash_bytes.extend(piece_hash)  # Add final hash bytes
    
    # Set the pieces field to the concatenated hash bytes
    metainfo["info"]["pieces"] = bytes(pieces_hash_bytes)
    
    logging.info(f"Creating torrent with metainfo: {metainfo}")
    encoded_info = bencodepy.encode(metainfo["info"])
    metainfo["torrent_hash"] = hashlib.sha1(encoded_info).hexdigest()
    
    with open(output_path, "wb") as f:
        f.write(bencodepy.encode(metainfo))
    
    logging.info(f"Torrent file created: {output_path}")
    return output_path