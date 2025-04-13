# Simple Like-Torrent Application

This is a BitTorrent-like file-sharing application developed for the "Computer Networks" course (Semester 1, 2023-2024). It implements a peer-to-peer file-sharing system with a centralized HTTP tracker, a Tkinter-based GUI, SQLite database persistence, and support for multi-file torrents. Clients automatically download files from peers and seed (upload) to others after completion, adhering to the assignment's requirements.

## Features
- **Tracker Protocol**: HTTP-based tracker to register peers, manage torrent metadata, and provide peer lists.
- **Torrent Download/Upload**: Concurrent downloading of multi-file torrents from multiple peers; automatic seeding after download completion.
- **GUI**: Tkinter interface to select torrent files, set download directories, pause/stop/resume downloads, and view detailed statistics (peers, files, states).
- **Database Persistence**: SQLite stores torrent metadata, peer states (downloading, paused, stopped, seeding), piece ownership, and peer interactions for resuming across sessions.
- **Magnet Text**: Generates magnet links for torrents, included in tracker requests.
- **Extra Credit**: Tracker scrape endpoint to retrieve torrent statistics (complete, incomplete peers).
- **Multi-File Support**: Handles torrents with multiple files, mapping pieces to file offsets correctly.

## Requirements
- **Python**: 3.8 or higher.
- **Libraries**:
  - `flask`: For the tracker server.
  - `flask-cors`: For cross-origin requests.
  - `requests`: For HTTP communication.
  - `tkinter`: For the GUI (included with Python; may need installation on Linux, e.g., `sudo apt-get install python3-tk`).
- Install dependencies:
  ```bash
  pip install flask flask-cors requests

## Project structure
```plaintext
simple-like-torrent/
├── client.py         # Client logic for downloading and seeding
├── config.py         # Configuration (ports, piece size)
├── metainfo.py       # Torrent file creation and loading
├── peer.py           # Peer connection handling
├── piece_manager.py  # Piece and file management
├── tracker.py        # HTTP tracker server
├── ui.py             # Tkinter GUI
├── tests/            # Unit tests
│   ├── __init__.py
│   ├── test_tracker.py
│   ├── test_client.py
│   ├── test_download.py
│   ├── test_upload.py
│   ├── test_ui.py
│   └── test_scrape.py
├── downloads/        # Default download directory (created automatically)
├── torrent.db        # SQLite database (created on first run)
├── requirements.txt  # Python dependencies
└── README.md         # This file
```
## Setup
### Clone the repository 
```python
git clone <repository-url>
cd simple-like-torrent
```
### Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```
### Install dependencies
```bash
pip install -r requirements.txt
```
### Create a torrent file
* For a single file:
```bash
python metainfo.py sample1.txt http://localhost:8000 sample.torrent
```
* For multiple files:
```bash
python metainfo.py "sample1.txt sample2.txt" http://localhost:8000 multi.torrent
```
## Running the application
### Start the tracker
```bash
python tracker.py
```
### Run a client
```bash
python ui.py
```
### Testing seeding (Optional)
```bash
python client.py sample.torrent --seed
```