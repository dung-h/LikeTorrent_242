# File: src/tracker_ui.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import sys
import os
import threading
import logging
import time
import json
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from matplotlib import pyplot as plt

# Add the src directory to the path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.tracker.tracker import Tracker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LikeTorrent Tracker")
        self.root.geometry("800x600")  # Increased window size for better display
        self.tracker = Tracker()
        self.running = True
        self.ui_lock = threading.Lock()
    
        # Main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Overview tab
        self.overview_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_tab, text="Overview")
        
        # Stats frame in overview tab
        self.stats_frame = ttk.Frame(self.overview_tab)
        self.stats_frame.pack(fill=tk.X, pady=5)
        self.peer_count = ttk.Label(self.stats_frame, text="Peers: 0")
        self.peer_count.pack(side=tk.LEFT, padx=5)
        self.torrent_count = ttk.Label(self.stats_frame, text="Torrents: 0")
        self.torrent_count.pack(side=tk.LEFT, padx=5)
        self.announce_label = ttk.Label(self.stats_frame, text="Announces: 0")
        self.announce_label.pack(side=tk.LEFT, padx=5)
        self.bandwidth_label = ttk.Label(self.stats_frame, text="Total: 0 KB/s ↓ | 0 KB/s ↑")
        self.bandwidth_label.pack(side=tk.LEFT, padx=5)
        
        # Graph for overall bandwidth
        self.fig, self.ax = plt.subplots(figsize=(8, 4))  # Larger graph for better visibility
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.overview_tab)
        self.canvas.get_tk_widget().pack(pady=5, fill=tk.BOTH, expand=True)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Speed (KB/s)")
        self.ax.grid(True)
        
        # Setup data for graph
        self.speed_history = {"download": [], "upload": []}
        self.time_history = []
        
        # Peers tab
        self.peers_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.peers_tab, text="Peers")
        
        # Enhanced peer table with rates
        self.peers_tree = ttk.Treeview(self.peers_tab, 
            columns=("PeerID", "IP", "Port", "Torrent", "Event", "Downloaded", "Uploaded", "DownRate", "UpRate"), 
            show="headings")
        self.peers_tree.heading("PeerID", text="Peer ID")
        self.peers_tree.heading("IP", text="IP Address")
        self.peers_tree.heading("Port", text="Port")
        self.peers_tree.heading("Torrent", text="Torrent Hash")
        self.peers_tree.heading("Event", text="Status")  # Changed to Status for clarity
        self.peers_tree.heading("Downloaded", text="Downloaded (MB)")
        self.peers_tree.heading("Uploaded", text="Uploaded (MB)")
        self.peers_tree.heading("DownRate", text="Down KB/s")
        self.peers_tree.heading("UpRate", text="Up KB/s")
        
        # Set column widths for peers
        self.peers_tree.column("PeerID", width=100)
        self.peers_tree.column("IP", width=100)
        self.peers_tree.column("Port", width=60)
        self.peers_tree.column("Torrent", width=100)
        self.peers_tree.column("Event", width=120)  # Widened for status+type
        self.peers_tree.column("Downloaded", width=120)
        self.peers_tree.column("Uploaded", width=120)
        self.peers_tree.column("DownRate", width=80)
        self.peers_tree.column("UpRate", width=80)
        
        # Add scrollbar and packing for peers
        self.peers_scrollbar = ttk.Scrollbar(self.peers_tab, orient=tk.VERTICAL, command=self.peers_tree.yview)
        self.peers_tree.configure(yscrollcommand=self.peers_scrollbar.set)
        self.peers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.peers_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Torrents tab
        self.torrents_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.torrents_tab, text="Torrents")
        
        # Torrent table
        self.torrents_tree = ttk.Treeview(self.torrents_tab, 
            columns=("Hash", "Peers", "Complete", "Incomplete", "Downloaded", "Uploaded"), 
            show="headings")
        
        # FIXED: Setting headings on the correct tree
        self.torrents_tree.heading("Hash", text="Torrent Hash")
        self.torrents_tree.heading("Peers", text="Peers")
        self.torrents_tree.heading("Complete", text="Complete")
        self.torrents_tree.heading("Incomplete", text="Incomplete")
        self.torrents_tree.heading("Downloaded", text="Downloaded (MB)")  # Fixed
        self.torrents_tree.heading("Uploaded", text="Uploaded (MB)")      # Fixed
        
        # Set column widths for torrents
        self.torrents_tree.column("Hash", width=200)
        self.torrents_tree.column("Peers", width=60)
        self.torrents_tree.column("Complete", width=80)
        self.torrents_tree.column("Incomplete", width=80)
        self.torrents_tree.column("Downloaded", width=120)
        self.torrents_tree.column("Uploaded", width=120)
        
        # Add scrollbar and packing for torrents
        self.torrents_scrollbar = ttk.Scrollbar(self.torrents_tab, orient=tk.VERTICAL, command=self.torrents_tree.yview)
        self.torrents_tree.configure(yscrollcommand=self.torrents_scrollbar.set)
        self.torrents_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.torrents_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add search and filter controls
        self.filter_frame = ttk.Frame(self.main_frame)
        self.filter_frame.pack(fill=tk.X, pady=5)
        ttk.Label(self.filter_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(self.filter_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", self.filter_peers)
        
        # Status bar
        self.status_bar = ttk.Label(self.main_frame, text="Tracker running on port 8000", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Start server
        self.server_thread = threading.Thread(target=self.tracker.run, daemon=True)
        self.server_thread.start()
        
        # Start UI updates
        self.update_ui()
    def filter_peers(self, event=None):
        """Filter the peers list based on search input"""
        search_text = self.search_var.get().lower()
        
        # Clear and repopulate the peers tree with filtered results
        for item in self.peers_tree.get_children():
            self.peers_tree.delete(item)
        
        try:
            torrents = self.tracker.get_torrents()
            for torrent_hash, torrent_data in torrents.items():
                peers = torrent_data.get("peers", {})
                for peer_id, peer in peers.items():
                    # Check if search text matches any field
                    if (search_text in peer_id.lower() or 
                        search_text in str(peer.get("ip", "")).lower() or 
                        search_text in str(peer.get("port", "")) or 
                        search_text in torrent_hash.lower() or
                        search_text in str(peer.get("event", "")).lower()):
                        
                        try:
                            # Convert values to float to ensure they're numbers
                            download_rate = float(peer.get("download_rate", 0))
                            upload_rate = float(peer.get("upload_rate", 0))
                            downloaded = float(peer.get("downloaded", 0))
                            uploaded = float(peer.get("uploaded", 0))
                            
                            self.peers_tree.insert("", tk.END, values=(
                                peer_id[:10] + "..." if len(peer_id) > 10 else peer_id,
                                peer.get("ip", "unknown"),
                                peer.get("port", "unknown"),
                                torrent_hash[:10] + "..." if len(torrent_hash) > 10 else torrent_hash,
                                peer.get("event", "unknown"),
                                f"{downloaded/1024/1024:.2f} MB",
                                f"{uploaded/1024/1024:.2f} MB",
                                f"{download_rate:.2f}",
                                f"{upload_rate:.2f}"
                            ))
                        except Exception as e:
                            logging.error(f"Error displaying peer {peer_id}: {e}")
        except Exception as e:
            logging.error(f"Filter error: {e}")

        # Add a method to identify peer type (seeder/leecher) based on their stats
    def get_peer_type(self, peer):
        downloaded = float(peer.get("downloaded", 0))
        uploaded = float(peer.get("uploaded", 0))
        event = peer.get("event", "").lower()
        seeding_flag = peer.get("seeding", False)  # New field client sends
        
        # Consider a peer a seeder if:
        # 1. Their event is "completed"
        # 2. They've uploaded more than they've downloaded
        # 3. They explicitly report seeding=True
        # 4. They have a "started" event but are no longer downloading (rate near 0)
        if (event == "completed" or 
            uploaded > downloaded or 
            seeding_flag or 
            (event == "started" and float(peer.get("download_rate", 0)) < 0.1 and downloaded > 0)):
            return "Seeder"
        else:
            return "Leecher"
    def update_ui(self):
        if not self.running:
            return
        try:
            with self.ui_lock:
                # Clear existing entries
                for item in self.peers_tree.get_children():
                    self.peers_tree.delete(item)
                for item in self.torrents_tree.get_children():
                    self.torrents_tree.delete(item)
                
                # Update torrents and peers
                try:
                    torrents = self.tracker.get_torrents()
                    total_download_rate = 0
                    total_upload_rate = 0
                    peer_count = 0
                    
                    # Process each torrent
                    for torrent_hash, torrent_data in torrents.items():
                        # Extract peers from the torrent data
                        peers = torrent_data.get("peers", {})
                        
                        complete = sum(1 for p in peers.values() if p.get("event") == "completed")
                        incomplete = len(peers) - complete
                        total_down = sum(p.get("downloaded", 0) for p in peers.values())
                        total_up = sum(p.get("uploaded", 0) for p in peers.values())
                        
                        # Add torrent to torrent tree
                        self.torrents_tree.insert("", tk.END, values=(
                            torrent_hash[:15] + "..." if len(torrent_hash) > 15 else torrent_hash,
                            len(peers),
                            complete,
                            incomplete,
                            f"{total_down/1024/1024:.2f} MB",
                            f"{total_up/1024/1024:.2f} MB"
                        ))
                        
                        # Process peers for this torrent
                        for peer_id, peer in peers.items():
                            try:
                                download_rate = float(peer.get("download_rate", 0))
                                upload_rate = float(peer.get("upload_rate", 0))
                                downloaded = float(peer.get("downloaded", 0))
                                uploaded = float(peer.get("uploaded", 0))
                                
                                peer_type = self.get_peer_type(peer)
                                
                                total_download_rate += download_rate
                                total_upload_rate += upload_rate
                                
                                # Add to peer tree with rate info
                                self.peers_tree.insert("", tk.END, values=(
                                    peer_id[:10] + "..." if len(peer_id) > 10 else peer_id,
                                    peer.get("ip", "unknown"),
                                    peer.get("port", "unknown"),
                                    torrent_hash[:10] + "..." if len(torrent_hash) > 10 else torrent_hash,
                                    f"{peer.get('event', 'unknown')} ({peer_type})",
                                    f"{downloaded/1024/1024:.2f} MB",
                                    f"{uploaded/1024/1024:.2f} MB",
                                    f"{download_rate:.2f}",
                                    f"{upload_rate:.2f}"
                                ))
                                peer_count += 1
                            except Exception as peer_error:
                                logging.error(f"Error processing peer {peer_id}: {peer_error}")
                    
                    # Update summary labels
                    self.peer_count.config(text=f"Peers: {peer_count}")
                    self.torrent_count.config(text=f"Torrents: {len(torrents)}")
                    self.announce_label.config(text=f"Announces: {self.tracker.announce_count}")
                    self.bandwidth_label.config(text=f"Total: {total_download_rate:.2f} KB/s ↓ | {total_upload_rate:.2f} KB/s ↑")
                    
                    # Rest of the graph update code...
                    if not hasattr(self, 'first_time') or self.first_time is None:
                        self.first_time = time.time()
                        self.time_history = [0]
                        self.speed_history["download"] = [0]
                        self.speed_history["upload"] = [0]
                        self.point_count = 1
                    
                    # Add new data point with consistent indexing
                    self.point_count += 1
                    self.speed_history["download"].append(total_download_rate)
                    self.speed_history["upload"].append(total_upload_rate)
                    self.time_history.append(self.point_count - 1)  # Use a simple counter for x-axis
                    
                    # Ensure all arrays have the same length
                    min_len = min(len(self.time_history), 
                                  len(self.speed_history["download"]), 
                                  len(self.speed_history["upload"]))
                    
                    if min_len < len(self.time_history):
                        self.time_history = self.time_history[:min_len]
                    if min_len < len(self.speed_history["download"]):
                        self.speed_history["download"] = self.speed_history["download"][:min_len]
                    if min_len < len(self.speed_history["upload"]):
                        self.speed_history["upload"] = self.speed_history["upload"][:min_len]
                    
                    # Maximum history length
                    max_history = 300
                    if len(self.time_history) > max_history:
                        self.time_history = self.time_history[-max_history:]
                        self.speed_history["download"] = self.speed_history["download"][-max_history:]
                        self.speed_history["upload"] = self.speed_history["upload"][-max_history:]
                    
                except Exception as data_error:
                    logging.error(f"Error processing tracker data: {data_error}")
                    self.status_bar.config(text=f"Data error: {data_error}")
                        
                # Update the graph
                try:
                    self.ax.clear()
                    if len(self.time_history) > 1:  # Only plot if we have at least 2 points
                        # Double-check lengths for plotting - shouldn't be needed but just in case
                        plot_len = min(len(self.time_history), 
                                      len(self.speed_history["download"]), 
                                      len(self.speed_history["upload"]))
                        
                        x_data = self.time_history[:plot_len]
                        download_data = self.speed_history["download"][:plot_len]
                        upload_data = self.speed_history["upload"][:plot_len]
                        
                        self.ax.plot(x_data, download_data, label="Download", color="#4682B4")
                        self.ax.plot(x_data, upload_data, label="Upload", color="#FFA500")
                        self.ax.legend()
                    self.ax.set_xlabel("Time (s)")
                    self.ax.set_ylabel("Speed (KB/s)")
                    self.ax.grid(True)
                    self.canvas.draw()
                except Exception as graph_error:
                    logging.error(f"Graph error: {graph_error}")
                    
        except Exception as e:
            logging.error(f"Tracker UI update error: {e}")
            self.status_bar.config(text=f"Error: {e}")
        
        self.root.after(1000, self.update_ui)
if __name__ == "__main__":
    root = tk.Tk()
    app = TrackerGUI(root)
    root.mainloop()