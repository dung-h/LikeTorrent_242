# LikeTorrent
A simple BitTorrent-like application built for the Computer Networks course.

## Setup
1. Run the tracker: `python tracker.py`
2. Create a torrent file:
   ```python
   from metainfo import Metainfo
   meta = Metainfo("sample.txt", "http://localhost:8000")
   meta.save("sample.torrent")