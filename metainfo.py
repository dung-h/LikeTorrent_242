# File: metainfo.py
import hashlib
import logging
import os
import sys
import bencodepy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_torrent(torrent_file):
    """Parse .torrent file into a metainfo dictionary."""
    if not os.path.exists(torrent_file):
        raise FileNotFoundError(f"Torrent file {torrent_file} not found")

    metainfo = {}
    try:
        with open(torrent_file, 'rb') as f:
            data = bencodepy.decode(f.read())

        # Populate metainfo
        metainfo['announce'] = data[b'announce'].decode()
        info = data[b'info']
        metainfo['torrent_hash'] = hashlib.sha1(bencodepy.encode(info)).hexdigest()
        metainfo['magnet'] = f"magnet:?xt=urn:btih:{metainfo['torrent_hash']}&tr={metainfo['announce']}"
        metainfo['piece_length'] = info[b'piece length']
        
        # Handle files (single or multi-file)
        if b'files' in info:
            metainfo['files'] = [
                {'path': '/'.join(p.decode() for p in file[b'path']), 'length': file[b'length']}
                for file in info[b'files']
            ]
        else:
            metainfo['files'] = [{'path': info[b'name'].decode(), 'length': info[b'length']}]

        # Convert pieces to list of SHA1 hashes
        pieces_raw = info[b'pieces']
        if len(pieces_raw) % 20 != 0:
            raise ValueError("Invalid pieces length")
        metainfo['pieces'] = [pieces_raw[i:i+20].hex() for i in range(0, len(pieces_raw), 20)]
        
        logging.info(f"Parsed torrent: {metainfo['files'][0]['path']}, {sum(f['length'] for f in metainfo['files'])} bytes, {len(metainfo['pieces'])} pieces")
        return metainfo
    except Exception as e:
        logging.error(f"Failed to parse torrent: {e}")
        raise

def create_torrent(input_file, tracker_url, output_torrent, piece_size=512*1024):
    """Create a .torrent file for the given input file."""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file {input_file} not found")

    info = {}
    
    # File details
    file_size = os.path.getsize(input_file)
    file_name = os.path.basename(input_file)
    info[b'name'] = file_name.encode()
    info[b'length'] = file_size
    info[b'piece length'] = piece_size

    # Compute piece hashes
    pieces = []
    with open(input_file, 'rb') as f:
        while True:
            piece = f.read(piece_size)
            if not piece:
                break
            pieces.append(hashlib.sha1(piece).digest())
    if not pieces:
        raise ValueError("File is empty or too small")
    info[b'pieces'] = b''.join(pieces)

    # Construct torrent dictionary
    torrent = {
        b'announce': tracker_url.encode(),
        b'info': info
    }

    # Write to output file
    try:
        with open(output_torrent, 'wb') as f:
            f.write(bencodepy.encode(torrent))
        logging.info(f"Created torrent: {output_torrent} for {file_name}, {file_size} bytes, {len(pieces)} pieces")
    except Exception as e:
        logging.error(f"Failed to create torrent: {e}")
        raise

if __name__ == '__main__':
    if len(sys.argv) == 4:
        # Create a torrent file
        input_file, tracker_url, output_torrent = sys.argv[1:4]
        try:
            create_torrent(input_file, tracker_url, output_torrent)
        except Exception as e:
            logging.error(f"Error creating torrent: {e}")
            sys.exit(1)
    elif len(sys.argv) == 2:
        # Parse a torrent file
        torrent_file = sys.argv[1]
        try:
            parse_torrent(torrent_file)
        except Exception as e:
            logging.error(f"Error parsing torrent: {e}")
            sys.exit(1)
    else:
        print("Usage:")
        print("  To create: python metainfo.py <input_file> <tracker_url> <output_torrent>")
        print("  To parse: python metainfo.py <torrent_file>")
        sys.exit(1)