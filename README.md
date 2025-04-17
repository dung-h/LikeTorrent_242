# LikeTorrent Application

This is a BitTorrent-like file-sharing application developed for the "Computer Networks" course (Semester 2, 2024-2025). It implements a peer-to-peer file-sharing system with a Flask-based HTTP tracker, a Tkinter-based GUI, and support for multi-file torrents. The application prioritizes a user-friendly GUI (`ui.py`) for managing torrents, with optional command-line support (`client.py`). Clients can download files, create torrents, and seed, meeting the assignment's requirements for UI (5%), downloading (30%), uploading (15%), and multi-file support.

## Features

* **Tracker Protocol:** Flask-based HTTP tracker (`/announce`, `/scrape`) manages peer registration and torrent tracking. Supports magnet links and `started`, `stopped`, `completed` events.
* **Torrent Download/Upload:**
    * Concurrent downloading from multiple peers with piece-to-file mapping for multi-file torrents.
    * Seeding after download or from user-selected directories.
    * Piece verification via SHA-1 hashes.
    * **Automatic Leecher-to-Seeder Transition:** Completed downloads automatically become seeders.
* **GUI (`ui.py`):**
    * Add, create, and manage torrents in a queue.
    * Control downloads/seeding (start, pause, resume, stop).
    * **Custom Port Selection:** Configure unique ports for each torrent to prevent collisions.
    * Tabs for:
        * **Overview:** Progress (%), state, speed graph (download/upload).
        * **Peers:** IP, port, pieces downloaded/uploaded, speeds.
        * **Files:** File names, sizes, types, progress, and actions (open file/folder).
    * Context menus to kick peers or open files/folders.
    * Dark/light theme toggle.
* **Command-Line Support:** Optional `client.py` for downloading/seeding with specified paths.
* **Multi-File Support:** Correctly handles torrents with multiple files (e.g., two videos).
* **Multi-Instance Support:** Run multiple clients simultaneously on different ports.
* **Extra Credit:**
    * Tracker `/scrape` endpoint for statistics (complete/incomplete peers).
    * Simultaneous torrent management via GUI.
    * **Dynamic Peer Discovery:** Periodically queries tracker for new peers during downloads.
    * **Peer Selection:** Weighted peer selection based on success rate and download time, with basic rarest-first strategy.

## Known Issues and Fixes

* **Single Seeder Dominance:** Fixed by implementing a bitfield exchange to verify piece availability and prioritizing rarest pieces.
* **Incorrect Peer Count:** Resolved by cleaning up stale `peer_stats` entries and counting only active peers.
* **Speed Display Errors:** Improved by buffering bytes and using a moving average for smoother speed calculations.
* **Peer Discovery:** Enhanced with more frequent tracker queries (every 15s) and dynamic peer integration.
* **Port Collisions:** Resolved by adding custom port selection in the UI and preserving ports across client restarts.
* **Leecher-to-Seeder Transition:** Fixed issues where finished downloads weren't properly becoming seeders by improving the transition logic.

## Requirements

* **Python:** 3.8 or higher.
* **Libraries:**
    * `bencodepy`
    * `flask`
    * `flask-cors`
    * `requests`
    * `matplotlib`
    * `Pillow` (optional for icons)
    * `tkinter` (install on Linux: `sudo apt-get install python3-tk`)
* **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Project Structure
```plaintext
LikeTorrent/
├── src/
│   ├── peer/
│   │   ├── client.py          # Client logic for downloading/seeding
│   │   ├── config.py          # Configuration (ports, piece size)
│   │   ├── metainfo.py        # Torrent file parsing
│   │   ├── peer.py            # Peer connection handling
│   │   ├── piece_manager.py   # Piece and file management
│   │   └── torrent_maker.py   # Torrent file creation
│   ├── tracker/
│   │   └── tracker.py         # Flask-based HTTP tracker
│   ├── ui.py                  # Tkinter client GUI
│   └── tracker_ui.py          # Tkinter tracker GUI
├── requirements.txt
└── README.md
```
## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/dung-h/LikeTorrent_242.git
    cd LikeTorrent
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate   # Linux/Mac
    venv\Scripts\activate      # Windows
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

### Start the Tracker

1.  Navigate to the src directory:
    ```bash
    cd src
    ```
2.  Run the tracker GUI:
    ```bash
    python tracker_ui.py
    ```
    The tracker runs at `http://localhost:8000`, displaying peer and torrent information.

### Run the Client

1.  Run the client GUI:
    ```bash
    python ui.py
    ```
    Use the GUI to add torrents, create torrents, manage downloads/seeding, and view statistics.

### Command-Line Usage (Optional)

* **Download:**
    ```bash
    python peer/client.py path/to/torrent.torrent --base_path /path/to/download --download --port 6882
    ```
* **Seed:**
    ```bash
    python peer/client.py path/to/torrent.torrent --base_path /path/to/files --port 6883
    ```

### Creating a Torrent

1.  In the GUI, click "Create Torrent".
2.  Select files or directories to share.
3.  Enter the tracker URL (`http://localhost:8000`).
4.  Select a custom port for this torrent.
5.  Save the `.torrent` file.
6.  Add the `.torrent` file to the client to seed or download.

### Adding an Existing Torrent

1. In the GUI, click "Add Torrent".
2. Select the `.torrent` file.
3. Choose a unique port for this torrent to avoid collisions.
4. Select the download/seed location.
5. The torrent will automatically start seeding if files exist or begin downloading otherwise.

## Manual Testing

### Multi-Peer Simulation

1.  Start the tracker:
    ```bash
    python src/tracker_ui.py
    ```
2.  Create a torrent with multiple files via the GUI.
3.  Run multiple client instances (`python ui.py`) on different machines or terminals.
4.  Add the torrent to each client, selecting appropriate download/seed directories and different ports.
5.  Verify downloads complete, seeding occurs, and the tracker GUI shows correct peer information.
6.  Observe how completed downloads automatically transition to seeding.

## Assignment Compliance

* **Tracker Protocol (15%):** Fully implemented with magnet links, event reporting, and peer list parsing.
* **Torrent Download (30%):** Supports concurrent multi-peer downloads with multi-file mapping; improved with bitfield-based piece selection.
* **Torrent Upload (15%):** Handles multiple concurrent uploads and seeding with proper port handling.
* **User Interface (5%):** Comprehensive Tkinter GUI with detailed statistics and port configuration.
* **Readme (5%):** Updated to reflect GUI focus, port handling, and bug fixes.
* **Extra Credit (10%):** Implements tracker `/scrape`, simultaneous torrents, and custom port selection.

## Future Improvements

* Implement advanced strategies (e.g., Super Seeding, End Game).
* Add Distributed Hash Table (DHT) support.
* Optimize peer selection with "4+1" peer limits and tit-for-tat.
* Implement UPnP for automatic port forwarding.
