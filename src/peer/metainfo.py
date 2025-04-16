# File: metainfo.py
import bencodepy
import hashlib
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_torrent(torrent_file):
    try:
        with open(torrent_file, "rb") as f:
            data = f.read()
            logging.info(f"Parsing torrent file: {torrent_file}, size: {len(data)} bytes")
            metainfo = bencodepy.decode(data)
        
        if not isinstance(metainfo, dict):
            raise ValueError("Invalid torrent: not a dictionary")
        
        if b"info" not in metainfo:
            raise ValueError("Invalid torrent: missing 'info'")
        
        info = metainfo[b"info"]
        if not isinstance(info, dict):
            raise ValueError("Invalid torrent: 'info' not a dictionary")
        
        piece_length = info.get(b"piece_length")
        if not isinstance(piece_length, int):
            logging.error(f"Invalid piece_length: {piece_length}")
            raise ValueError("Invalid torrent: 'piece_length' must be an integer")
        
        pieces = info.get(b"pieces", b"")
        if not isinstance(pieces, bytes):
            raise ValueError("Invalid torrent: 'pieces' must be bytes")
        
        piece_hashes = [pieces[i:i+20].hex() for i in range(0, len(pieces), 20)]
        
        result = {
            "announce": metainfo.get(b"announce", b"").decode("utf-8"),
            "piece_length": piece_length,
            "pieces": piece_hashes,
            "torrent_hash": hashlib.sha1(bencodepy.encode(info)).hexdigest()
        }
        
        if b"files" in info:
            result["files"] = [
                {
                    "length": f[b"length"],
                    "path": os.path.join(*[p.decode("utf-8") for p in f[b"path"]])
                }
                for f in info[b"files"]
            ]
        else:
            result["files"] = [{"length": info[b"length"], "path": info[b"name"].decode("utf-8")}]
        
        logging.info(f"Parsed torrent: hash={result['torrent_hash']}, files={[f['path'] for f in result['files']]}")
        return result
    
    except Exception as e:
        logging.error(f"Failed to parse torrent: {e}")
        raise