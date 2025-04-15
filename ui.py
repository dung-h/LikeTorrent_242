# File: ui.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from client import Client
import threading
import time
import os
from PIL import Image, ImageTk
import queue

class TorrentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LikeTorrent Client")
        self.root.geometry("700x550")
        self.root.minsize(600, 450)
        self.client = None
        self.torrent_file = None
        self.running = False
        self.download_thread = None
        self.seed_thread = None
        self.event_queue = queue.Queue()

        # Style configuration
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Arial", 10), padding=6, background="#4682B4", foreground="black")
        style.map("TButton", background=[("active", "#5A9BD4")])
        style.configure("TLabel", font=("Arial", 10), background="#2e2e2e", foreground="white")
        style.configure("Treeview", font=("Arial", 9), rowheight=25, background="#333333", foreground="white", fieldbackground="#333333")
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"), background="#444444", foreground="white")
        style.configure("TNotebook", background="#2e2e2e", tabmargins=2)
        style.configure("TProgressbar", thickness=20, troughcolor="#555555", background="#4682B4")
        style.configure("TFrame", background="#2e2e2e")

        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Status bar
        self.status_bar = ttk.Label(self.main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Torrent selection
        self.select_frame = ttk.Frame(self.main_frame)
        self.select_frame.pack(fill=tk.X, pady=5)
        self.torrent_label = ttk.Label(self.select_frame, text="No torrent selected")
        self.torrent_label.pack(side=tk.LEFT)
        self.select_btn = ttk.Button(self.select_frame, text="Select Torrent", command=self.select_torrent)
        self.select_btn.pack(side=tk.RIGHT)

        # Control buttons
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(self.control_frame, text="Start", command=self.start_download, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(self.control_frame, text="Stop", command=self.stop_client, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Tabbed interface
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Overview tab
        self.overview_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_tab, text="Overview")
        self.state_label = ttk.Label(self.overview_tab, text="State: Stopped")
        self.state_label.pack(pady=5)
        self.progress_label = ttk.Label(self.overview_tab, text="Progress: 0%")
        self.progress_label.pack(pady=5)
        self.progress_bar = ttk.Progressbar(self.overview_tab, length=500, mode="determinate")
        self.progress_bar.pack(pady=5)
        self.speed_label = ttk.Label(self.overview_tab, text="Speed: 0 KB/s")
        self.speed_label.pack(pady=5)
        self.peers_summary = ttk.Label(self.overview_tab, text="Peers: 0")
        self.peers_summary.pack(pady=5)

        # Peers tab
        self.peers_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.peers_tab, text="Peers")
        self.peers_tree = ttk.Treeview(self.peers_tab, columns=("IP", "Port", "Speed", "Pieces"), show="headings")
        self.peers_tree.heading("IP", text="IP Address")
        self.peers_tree.heading("Port", text="Port")
        self.peers_tree.heading("Speed", text="Speed (KB/s)")
        self.peers_tree.heading("Pieces", text="Pieces Shared")
        self.peers_tree.column("IP", width=150)
        self.peers_tree.column("Port", width=80)
        self.peers_tree.column("Speed", width=100)
        self.peers_tree.column("Pieces", width=100)
        self.peers_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.peers_scroll = ttk.Scrollbar(self.peers_tab, orient=tk.VERTICAL, command=self.peers_tree.yview)
        self.peers_tree.configure(yscrollcommand=self.peers_scroll.set)
        self.peers_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Files tab
        self.files_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.files_tab, text="Files")
        self.files_frame = ttk.Frame(self.files_tab)
        self.files_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.files_label = ttk.Label(self.files_frame, text="Downloaded Files:")
        self.files_label.pack(anchor=tk.W)
        self.files_tree = ttk.Treeview(self.files_frame, columns=("File", "Size", "Type", "Action"), show="headings")
        self.files_tree.heading("File", text="File Name")
        self.files_tree.heading("Size", text="Size (MB)")
        self.files_tree.heading("Type", text="Type")
        self.files_tree.heading("Action", text="Action")
        self.files_tree.column("File", width=200)
        self.files_tree.column("Size", width=100)
        self.files_tree.column("Type", width=80)
        self.files_tree.column("Action", width=80)
        self.files_tree.pack(fill=tk.BOTH, expand=True)
        self.files_scroll = ttk.Scrollbar(self.files_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=self.files_scroll.set)
        self.files_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load icons (optional)
        try:
            self.file_icon = ImageTk.PhotoImage(Image.open("file_icon.png").resize((16, 16)))
            self.torrent_icon = ImageTk.PhotoImage(Image.open("torrent_icon.png").resize((16, 16)))
        except:
            self.file_icon = None
            self.torrent_icon = None

        # Bind file click
        self.files_tree.bind("<Double-1>", self.files_tree_click)

        # Update UI
        self.update_ui()

    def select_torrent(self):
        self.torrent_file = filedialog.askopenfilename(filetypes=[("Torrent files", "*.torrent")])
        if self.torrent_file:
            self.torrent_label.config(text=f"Selected: {os.path.basename(self.torrent_file)}")
            self.status_bar.config(text="Torrent loaded")
            self.start_btn.config(state=tk.NORMAL)
            if self.client:
                self.stop_client()
            try:
                self.client = Client(self.torrent_file, port=6881)
                self.state_label.config(text=f"State: {self.client.state.capitalize()}")
                self.event_queue.put(("state", self.client.state))
                self.update_files_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load torrent: {e}")
                self.torrent_file = None
                self.torrent_label.config(text="No torrent selected")
                self.status_bar.config(text="Error loading torrent")
                self.start_btn.config(state=tk.DISABLED)

    def start_download(self):
        if not self.client or not self.torrent_file:
            messagebox.showwarning("Warning", "No torrent selected")
            return
        if self.download_thread and self.download_thread.is_alive():
            self.status_bar.config(text="Download already running")
            return
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_bar.config(text="Starting download...")
        self.download_thread = threading.Thread(target=self.client.start_download, daemon=False)
        self.seed_thread = threading.Thread(target=self.client.listen_for_requests, daemon=False)
        self.download_thread.start()
        self.seed_thread.start()
        self.event_queue.put(("state", "downloading"))

    def stop_client(self):
        if self.client:
            self.client.stop()
            self.running = False
            if self.download_thread and self.download_thread.is_alive():
                self.download_thread.join(timeout=5.0)
            if self.seed_thread and self.seed_thread.is_alive():
                self.seed_thread.join(timeout=5.0)
            self.download_thread = None
            self.seed_thread = None
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            # Clear event queue
            while not self.event_queue.empty():
                try:
                    self.event_queue.get_nowait()
                except queue.Empty:
                    break
            self.event_queue.put(("state", "stopped"))
            self.state_label.config(text="State: Stopped")
            self.progress_bar["value"] = 0
            self.speed_label.config(text="Speed: 0 KB/s")
            self.status_bar.config(text="Client stopped")
            # Reset client
            self.client = Client(self.torrent_file, port=6881) if self.torrent_file else None

    def open_file(self, file_path):
        try:
            os.startfile(file_path)
            self.status_bar.config(text=f"Opened {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")
            self.status_bar.config(text="Error opening file")

    def update_files_list(self):
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        if self.client:
            for file_info in self.client.metainfo["files"]:
                file_path = os.path.join(self.client.piece_manager.download_dir, file_info["path"])
                file_name = os.path.basename(file_path)
                size_mb = file_info["length"] / 1024 / 1024
                file_type = os.path.splitext(file_name)[1][1:].upper() or "Unknown"
                action = "Open" if os.path.exists(file_path) and self.client.piece_manager.all_pieces_downloaded() else ""
                self.files_tree.insert("", tk.END, values=(file_name, f"{size_mb:.2f}", file_type, action))

    def update_ui(self):
        if self.client:
            try:
                # State updates
                while not self.event_queue.empty():
                    event_type, value = self.event_queue.get_nowait()
                    if event_type == "state":
                        self.state_label.config(text=f"State: {value.capitalize()}")

                # Progress
                pieces_done = sum(self.client.piece_manager.have_pieces)
                total_pieces = self.client.piece_manager.total_pieces
                progress = (pieces_done / total_pieces * 100) if total_pieces > 0 else 0
                self.progress_bar["value"] = progress
                self.progress_label.config(text=f"Progress: {progress:.1f}%")
                self.peers_summary.config(text=f"Peers: {len(self.client.peers)}")

                # Speed
                speed = self.client.get_speed() if self.running else 0.0
                self.speed_label.config(text=f"Speed: {speed:.2f} KB/s")

                # Peers
                for item in self.peers_tree.get_children():
                    self.peers_tree.delete(item)
                for peer in self.client.peers:
                    speed = 0  # Placeholder
                    pieces = 0  # Placeholder
                    self.peers_tree.insert("", tk.END, values=(peer["ip"], peer["port"], f"{speed:.2f}", pieces))

                # Files
                self.update_files_list()

                # Status bar
                self.status_bar.config(text="Running..." if self.running else "Idle")
            except Exception as e:
                self.status_bar.config(text=f"Error: {e}")
        self.root.after(300, self.update_ui)  # Faster updates

    def files_tree_click(self, event):
        item = self.files_tree.selection()
        if item:
            values = self.files_tree.item(item)["values"]
            if values[3] == "Open":
                file_path = os.path.join(self.client.piece_manager.download_dir, values[0])
                self.open_file(file_path)

if __name__ == "__main__":
    root = tk.Tk()
    root.configure(bg="#2e2e2e")
    app = TorrentGUI(root)
    root.mainloop()