# File: ui.py
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import sqlite3
from client import TorrentClient

class TorrentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Like-Torrent Client")
        self.client = None

        tk.Label(root, text="Torrent File:").grid(row=0, column=0)
        self.torrent_entry = tk.Entry(root, width=50)
        self.torrent_entry.grid(row=0, column=1)
        tk.Button(root, text="Browse", command=self.browse_torrent).grid(row=0, column=2)

        tk.Label(root, text="Save To:").grid(row=1, column=0)
        self.dir_entry = tk.Entry(root, width=50)
        self.dir_entry.grid(row=1, column=1)
        tk.Button(root, text="Browse", command=self.browse_dir).grid(row=1, column=2)

        tk.Button(root, text="Start", command=self.start_client).grid(row=2, column=0)
        tk.Button(root, text="Pause", command=self.pause_client).grid(row=2, column=1)
        tk.Button(root, text="Stop", command=self.stop_client).grid(row=2, column=2)

        self.progress_label = tk.Label(root, text="Progress: 0/0 pieces")
        self.progress_label.grid(row=3, column=0, columnspan=3)
        self.stats_text = tk.Text(root, height=10, width=60)
        self.stats_text.grid(row=4, column=0, columnspan=3)

    def browse_torrent(self):
        filename = filedialog.askopenfilename(filetypes=[("Torrent files", "*.torrent")])
        if filename:
            self.torrent_entry.delete(0, tk.END)
            self.torrent_entry.insert(0, filename)

    def browse_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)

    def start_client(self):
        torrent_file = self.torrent_entry.get()
        download_dir = self.dir_entry.get()
        if not torrent_file or not download_dir:
            messagebox.showerror("Error", "Select torrent and directory")
            return
        self.client = TorrentClient(torrent_file)
        self.client.piece_manager.download_dir = download_dir
        threading.Thread(target=self.client.start_upload, daemon=True).start()
        threading.Thread(target=self.client.start_download, daemon=True).start()
        threading.Thread(target=self.update_stats, daemon=True).start()

    def pause_client(self):
        if self.client:
            self.client.pause()
            self.progress_label.config(text="Paused")

    def stop_client(self):
        if self.client:
            self.client.stop()
            self.progress_label.config(text="Stopped")

    def update_stats(self):
        db = sqlite3.connect('torrent.db')
        while self.client and self.client.running:
            pieces_done = sum(self.client.piece_manager.have_pieces)
            total_pieces = self.client.piece_manager.total_pieces
            self.progress_label.config(text=f"Progress: {pieces_done}/{total_pieces} pieces")
            c = db.cursor()
            c.execute('SELECT ip, port, state FROM peers WHERE peer_id != ?',
                      (self.client.peer_id,))
            peers = c.fetchall()
            c.execute('SELECT path, length FROM files WHERE torrent_hash = ?',
                      (self.client.metainfo["torrent_hash"],))
            files = c.fetchall()
            stats = f"State: {self.client.state}\nPeers: {len(peers)}\n"
            stats += "\nPeer Details:\n" + "\n".join(f"IP: {p[0]}:{p[1]}, State: {p[2]}" for p in peers)
            stats += "\nFiles:\n" + "\n".join(f"{f[0]} ({f[1]} bytes)" for f in files)
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, stats)
            time.sleep(1)
        db.close()
        
if __name__ == "__main__":
    root = tk.Tk()
    app = TorrentGUI(root)
    root.mainloop()