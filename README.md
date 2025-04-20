# LikeTorrent Application

This is a BitTorrent-like file-sharing application developed for the "Computer Networks" CO3093 course (Semester 2, 2024-2025). It implements a peer-to-peer file-sharing system with a Flask-based HTTP tracker, a Tkinter-based GUI, and support for multi-file torrents.

## Implemented Features

* **Tracker Protocol:** 
    * Flask-based HTTP tracker with `/announce` and `/scrape` endpoints
    * Peer registration and torrent tracking with SQLite database
    * Support for event reporting (`started`, `stopped`, `completed`)

* **Torrent Download:**
    * Piece-level downloading with SHA-1 hash verification
    * Bitfield exchange to determine peer piece availability
    * Rarest-first piece selection strategy
    * Concurrent downloads with multiple worker threads

* **Torrent Upload:**
    * Seeding with upload slot management using round-robin rotation
    * Upload speed tracking and reporting to tracker
    * Automatic leecher-to-seeder transition when download completes

* **User Interface:**
    * **Client GUI (`ui.py`):**
        * Queue-based torrent management
        * Overview tab with progress bar and speed graphs
        * Peers tab showing connection details and transfer statistics
        * Files tab with progress indicators and file actions
        * Dark/light theme toggle
    * **Tracker GUI (`tracker_ui.py`):**
        * Real-time visualization of connected peers
        * Torrent statistics monitoring
        * Network activity graphs
        * Peer type identification (seeder/leecher)

* **Advanced Features:**
    * Multi-file torrent support with correct piece-to-file mapping
    * Custom port selection to allow multiple client instances
    * Weighted peer selection based on past performance
    * Optimistic unchoking for fair upload distribution

## Requirements

* **Python:** 3.8 or higher
* **Libraries:**
    * `bencodepy` - For torrent file encoding/decoding
    * `flask` and `flask-cors` - For tracker implementation
    * `requests` - For HTTP communication
    * `matplotlib` - For speed graphs
    * `tkinter` - For GUI components
    * `Pillow` - For icon support (optional)

## Installation

```bash
# Clone repository
git clone https://github.com/dung-h/LikeTorrent_242.git
cd LikeTorrent_242

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

### Start the Tracker

```bash
cd src
python tracker_ui.py
```

The tracker will run at `http://localhost:8000` with a GUI interface showing connected peers and torrent information.

### Run the Client

```bash
cd src
python ui.py
```

The client GUI allows you to:
- Add or create torrents
- Start, pause, resume or stop downloads
- Monitor download/upload progress and speeds
- View connected peers and file information

### Command-Line Usage (Alternative)

```bash
# Download
python src/peer/client.py path/to/torrent.torrent --base_path /path/to/download --download --port 6882

# Seed
python src/peer/client.py path/to/torrent.torrent --base_path /path/to/files --port 6883
```

## Creating and Using Torrents

### Create a Torrent
1. In the client GUI, click "Create Torrent"
2. Select files to share
3. Enter tracker URL (`http://localhost:8000`)
4. Choose a custom port
5. Save the `.torrent` file

### Add an Existing Torrent
1. Click "Add Torrent"
2. Select the `.torrent` file
3. Choose a unique port
4. Select download location
5. The client will automatically start downloading or seeding

## Project Architecture

```
LikeTorrent_242/
├── src/
│   ├── peer/
│   │   ├── client.py          # Core client logic
│   │   ├── config.py          # Configuration settings
│   │   ├── metainfo.py        # Torrent file parser
│   │   ├── peer.py            # Peer connection handling
│   │   ├── piece_manager.py   # File piece management
│   │   └── torrent_maker.py   # Torrent file creation
│   ├── tracker/
│   │   └── tracker.py         # HTTP tracker implementation
│   ├── ui.py                  # Client GUI
│   └── tracker_ui.py          # Tracker GUI
├── requirements.txt
└── README.md
```

## Key Implementation Details

* **Bitfield Exchange:** Peers exchange bitfields to communicate piece availability
* **Piece Selection:** Implements rarest-first piece selection strategy
* **Upload Management:** Uses round-robin slot rotation for fair distribution
* **Port Selection:** Each torrent can use a unique port to prevent collisions
* **Peer Weighting:** Tracks peer performance to prioritize faster connections

## Testing

### Multi-Peer Testing
1. Start tracker (`python src/tracker_ui.py`)
2. Start multiple clients on different ports
3. Create and share a torrent with one client
4. Download with other clients
5. Observe both the downloading and seeding behaviors

The application includes comprehensive error handling and automatically transitions from downloading to seeding when a download completes.
