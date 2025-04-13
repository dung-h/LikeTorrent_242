CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    peer_id TEXT UNIQUE NOT NULL -- Links to client peer_id
);

CREATE TABLE torrents (
    torrent_hash TEXT PRIMARY KEY,
    tracker_url TEXT NOT NULL,
    piece_length INTEGER NOT NULL,
    total_pieces INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_hash TEXT NOT NULL,
    path TEXT NOT NULL,
    length INTEGER NOT NULL,
    start_offset INTEGER NOT NULL, -- For multi-file torrents
    FOREIGN KEY (torrent_hash) REFERENCES torrents(torrent_hash)
);

CREATE TABLE peers (
    peer_id TEXT PRIMARY KEY,
    ip TEXT NOT NULL,
    port INTEGER NOT NULL,
    state TEXT NOT NULL, -- 'downloading', 'seeding', 'paused', 'stopped'
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE peer_torrents (
    peer_id TEXT NOT NULL,
    torrent_hash TEXT NOT NULL,
    pieces_owned TEXT NOT NULL, -- JSON array of boolean or indices, e.g., '[true, false, ...]'
    downloaded_bytes INTEGER DEFAULT 0,
    state TEXT NOT NULL, -- 'downloading', 'paused', 'completed', 'seeding'
    PRIMARY KEY (peer_id, torrent_hash),
    FOREIGN KEY (peer_id) REFERENCES peers(peer_id),
    FOREIGN KEY (torrent_hash) REFERENCES torrents(torrent_hash)
);

CREATE TABLE peer_interactions (
    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_peer_id TEXT NOT NULL,
    target_peer_id TEXT NOT NULL,
    torrent_hash TEXT NOT NULL,
    piece_index INTEGER,
    bytes_transferred INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_peer_id) REFERENCES peers(peer_id),
    FOREIGN KEY (target_peer_id) REFERENCES peers(peer_id),
    FOREIGN KEY (torrent_hash) REFERENCES torrents(torrent_hash)
);