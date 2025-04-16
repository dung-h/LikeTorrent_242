# File: src/tracker_ui.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import sys
import os
import threading
import logging
import time
import json

# Add the src directory to the path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.tracker.tracker import Tracker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LikeTorrent Tracker")
        self.root.geometry("600x400")
        self.tracker = Tracker()
        self.running = True
        self.ui_lock = threading.Lock()

        # Main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Stats
        self.stats_frame = ttk.Frame(self.main_frame)
        self.stats_frame.pack(fill=tk.X, pady=5)
        self.peer_count = ttk.Label(self.stats_frame, text="Peers: 0")
        self.peer_count.pack(side=tk.LEFT, padx=5)
        self.torrent_count = ttk.Label(self.stats_frame, text="Torrents: 0")
        self.torrent_count.pack(side=tk.LEFT, padx=5)
        self.announce_label = ttk.Label(self.stats_frame, text="Announces: 0")
        self.announce_label.pack(side=tk.LEFT, padx=5)

        # Peer table
        self.tree = ttk.Treeview(self.main_frame, columns=("PeerID", "IP", "Port", "Torrent", "Event"), show="headings")
        self.tree.heading("PeerID", text="Peer ID")
        self.tree.heading("IP", text="IP Address")
        self.tree.heading("Port", text="Port")
        self.tree.heading("Torrent", text="Torrent Hash")
        self.tree.heading("Event", text="Event")
        self.tree.column("PeerID", width=150)
        self.tree.column("IP", width=100)
        self.tree.column("Port", width=80)
        self.tree.column("Torrent", width=150)
        self.tree.column("Event", width=80)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status_bar = ttk.Label(self.main_frame, text="Tracker starting...", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Start server
        self.server_thread = threading.Thread(target=self.tracker.run, daemon=True)
        self.server_thread.start()
        self.status_bar.config(text="Tracker running on port 8000")
        self.update_ui()

    def update_ui(self):
        if not self.running:
            return
        try:
            with self.ui_lock:
                for item in self.tree.get_children():
                    self.tree.delete(item)
                
                torrents = self.tracker.get_torrents()
                peer_count = 0
                for torrent_hash, peers in torrents.items():
                    for peer_id, peer in peers.items():
                        self.tree.insert("", tk.END, values=(
                            peer_id[:10] + "..." if len(peer_id) > 10 else peer_id,
                            peer["ip"],
                            peer["port"],
                            torrent_hash[:10] + "..." if len(torrent_hash) > 10 else torrent_hash,
                            peer["event"]
                        ))
                        peer_count += 1
                        logging.debug(f"Added peer {peer_id} for torrent {torrent_hash}")
                
                self.peer_count.config(text=f"Peers: {peer_count}")
                self.torrent_count.config(text=f"Torrents: {len(torrents)}")
                self.announce_label.config(text=f"Announces: {self.tracker.announce_count}")
        except Exception as e:
            logging.error(f"UI update error: {e}")
            self.status_bar.config(text=f"Error: {e}")
        
        self.root.after(1000, self.update_ui)

if __name__ == "__main__":
    root = tk.Tk()
    app = TrackerGUI(root)
    root.mainloop()