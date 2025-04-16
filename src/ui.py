# File: ui.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sys
import os
import threading
import time
from PIL import Image, ImageTk
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.peer.client import Client
from src.peer.torrent_maker import create_torrent_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TorrentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LikeTorrent Client")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)
        self.clients = {}
        self.paths = {}
        self.active_torrent = None
        self.torrent_file = None
        self.running = False
        self.download_thread = None
        self.seed_thread = None
        self.event_queue = queue.Queue()
        self.theme = "dark"
        self.speed_history = {"download": [], "upload": []}
        self.time_history = []
        self.down_speeds = []
        self.up_speeds = []
        self.DEFAULT_PATH = os.path.expanduser("~/Downloads")
        style = ttk.Style()
        
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.queue_frame = ttk.Frame(self.main_frame)
        self.queue_frame.pack(fill=tk.X, pady=5)
        self.queue_label = ttk.Label(self.queue_frame, text="Torrents:")
        self.queue_label.pack(side=tk.LEFT)
        self.queue_list = tk.Listbox(self.queue_frame, height=5, font=("Arial", 9))
        self.queue_list.pack(fill=tk.X, expand=True, padx=5)
        self.queue_list.bind("<<ListboxSelect>>", self.select_active_torrent)

        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.pack(fill=tk.X, pady=5)
        self.select_btn = ttk.Button(self.control_frame, text="Add Torrent", command=self.select_torrent)
        self.select_btn.pack(side=tk.LEFT, padx=5)
        self.create_btn = ttk.Button(self.control_frame, text="Create Torrent", command=self.create_torrent)
        self.create_btn.pack(side=tk.LEFT, padx=5)
        self.start_btn = ttk.Button(self.control_frame, text="Start", command=self.start_download, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.resume_btn = ttk.Button(self.control_frame, text="Resume", command=self.resume_client, state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=5)
        self.pause_btn = ttk.Button(self.control_frame, text="Pause", command=self.pause_client, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(self.control_frame, text="Stop", command=self.stop_client, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.theme_btn = ttk.Button(self.control_frame, text="Toggle Theme", command=self.toggle_theme)
        self.theme_btn.pack(side=tk.RIGHT, padx=5)

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        self.overview_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_tab, text="Overview")
        self.state_label = ttk.Label(self.overview_tab, text="State: Stopped")
        self.state_label.pack(pady=5)
        self.progress_label = ttk.Label(self.overview_tab, text="Progress: 0%")
        self.progress_label.pack(pady=5)
        self.progress_bar = ttk.Progressbar(self.overview_tab, length=600, mode="determinate")
        self.progress_bar.pack(pady=5)
        self.speed_label = ttk.Label(self.overview_tab, text="Speed: 0 KB/s")
        self.speed_label.pack(pady=5)
        self.peers_summary = ttk.Label(self.overview_tab, text="Peers: 0")
        self.peers_summary.pack(pady=5)
        
        self.fig, self.ax = plt.subplots(figsize=(6, 2))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.overview_tab)
        self.canvas.get_tk_widget().pack(pady=5)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Speed (KB/s)")
        self.ax.grid(True)

        self.peers_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.peers_tab, text="Peers")
        self.peers_tree = ttk.Treeview(self.peers_tab, columns=("IP", "Port", "DownPieces", "DownSpeed", "UpPieces", "UpSpeed"), show="headings")
        self.peers_tree.heading("IP", text="IP Address")
        self.peers_tree.heading("Port", text="Port")
        self.peers_tree.heading("DownPieces", text="Down Pieces")
        self.peers_tree.heading("DownSpeed", text="Down Speed (KB/s)")
        self.peers_tree.heading("UpPieces", text="Up Pieces")
        self.peers_tree.heading("UpSpeed", text="Up Speed (KB/s)")
        self.peers_tree.column("IP", width=150)
        self.peers_tree.column("Port", width=80)
        self.peers_tree.column("DownPieces", width=100)
        self.peers_tree.column("DownSpeed", width=100)
        self.peers_tree.column("UpPieces", width=100)
        self.peers_tree.column("UpSpeed", width=100)
        self.peers_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.peers_scroll = ttk.Scrollbar(self.peers_tab, orient=tk.VERTICAL, command=self.peers_tree.yview)
        self.peers_tree.configure(yscrollcommand=self.peers_scroll.set)
        self.peers_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.peers_tree.bind("<Button-3>", self.show_peer_menu)

        self.files_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.files_tab, text="Files")
        self.files_frame = ttk.Frame(self.files_tab)
        self.files_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.files_label = ttk.Label(self.files_frame, text="Files:")
        self.files_label.pack(anchor=tk.W)
        self.files_tree = ttk.Treeview(self.files_frame, columns=("File", "Size", "Type", "Progress", "Action"), show="headings")
        self.files_tree.heading("File", text="File Name")
        self.files_tree.heading("Size", text="Size (MB)")
        self.files_tree.heading("Type", text="Type")
        self.files_tree.heading("Progress", text="Progress")
        self.files_tree.heading("Action", text="Action")
        self.files_tree.column("File", width=200)
        self.files_tree.column("Size", width=100)
        self.files_tree.column("Type", width=80)
        self.files_tree.column("Progress", width=100)
        self.files_tree.column("Action", width=80)
        self.files_tree.pack(fill=tk.BOTH, expand=True)
        self.files_scroll = ttk.Scrollbar(self.files_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=self.files_scroll.set)
        self.files_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_tree.bind("<Double-1>", self.files_tree_click)
        self.files_tree.bind("<Button-3>", self.show_file_menu)

        self.peer_menu = tk.Menu(self.root, tearoff=0)
        self.peer_menu.add_command(label="Kick Peer", command=self.kick_peer)
        
        self.file_menu = tk.Menu(self.root, tearoff=0)
        self.file_menu.add_command(label="Open File", command=self.open_selected_file)
        self.file_menu.add_command(label="Open Folder", command=self.open_folder)

        self.status_bar = ttk.Label(self.main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        try:
            self.file_icon = ImageTk.PhotoImage(Image.open("file_icon.png").resize((16, 16)))
            self.torrent_icon = ImageTk.PhotoImage(Image.open("torrent_icon.png").resize((16, 16)))
        except:
            self.file_icon = None
            self.torrent_icon = None

        self.update_theme(style, "dark")
        self.update_ui()

    def update_theme(self, style, theme):
        self.theme = theme
        bg = "#2e2e2e" if theme == "dark" else "#f0f0f0"
        fg = "white" if theme == "dark" else "black"
        tree_bg = "#333333" if theme == "dark" else "#ffffff"
        tree_head = "#444444" if theme == "dark" else "#d3d3d3"
        style.configure("TButton", font=("Arial", 10), padding=6, background="#4682B4", foreground="black")
        style.map("TButton", background=[("active", "#5A9BD4")])
        style.configure("TLabel", font=("Arial", 10), background=bg, foreground=fg)
        style.configure("Treeview", font=("Arial", 9), rowheight=25, background=tree_bg, foreground=fg, fieldbackground=tree_bg)
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"), background=tree_head, foreground=fg)
        style.configure("TNotebook", background=bg)
        style.configure("TProgressbar", troughcolor="#555555" if theme == "dark" else "#d3d3d3", background="#4682B4")
        style.configure("TFrame", background=bg)
        self.root.configure(bg=bg)
        if hasattr(self, 'ax') and hasattr(self, 'fig'):
            self.ax.set_facecolor(tree_bg)
            self.fig.set_facecolor(bg)
            self.canvas.draw()

    def toggle_theme(self):
        self.update_theme(ttk.Style(), "light" if self.theme == "dark" else "dark")
        self.status_bar.config(text=f"Switched to {self.theme} theme")

    def select_torrent(self):
        torrent_file = filedialog.askopenfilename(filetypes=[("Torrent files", "*.torrent")])
        if torrent_file:
            base_path = filedialog.askdirectory(title="Select Download/Seed Location", initialdir=self.DEFAULT_PATH)
            if not base_path:
                messagebox.showwarning("Warning", "No location selected")
                return
            try:
                client = Client(torrent_file, base_path, port=6881)
                self.clients[torrent_file] = client
                self.paths[torrent_file] = base_path
                self.queue_list.insert(tk.END, os.path.basename(torrent_file))
                self.status_bar.config(text="Torrent added")
                if not self.active_torrent:
                    self.active_torrent = torrent_file
                    self.torrent_file = torrent_file
                if client.check_file_exists():
                    self.running = True
                    self.start_btn.config(state=tk.DISABLED)
                    self.pause_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.NORMAL)
                    self.seed_thread = threading.Thread(target=client.listen_for_requests, daemon=False)
                    self.seed_thread.start()
                    self.event_queue.put(("state", "seeding"))
                    self.status_bar.config(text="Seeding started")
                else:
                    self.start_btn.config(state=tk.NORMAL)
                self.update_files_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load torrent: {e}")
                self.status_bar.config(text="Error loading torrent")

    def create_torrent(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Torrent")
        dialog.geometry("400x300")
        
        ttk.Label(dialog, text="Select Files:").pack(pady=5)
        files_list = tk.Listbox(dialog, selectmode=tk.MULTIPLE, height=5)
        files_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        def add_files():
            files = filedialog.askopenfilenames()
            for f in files:
                files_list.insert(tk.END, f)
        
        ttk.Button(dialog, text="Add Files", command=add_files).pack(pady=5)
        
        ttk.Label(dialog, text="Tracker URL:").pack(pady=5)
        tracker_entry = ttk.Entry(dialog)
        tracker_entry.insert(0, "http://localhost:8000")
        tracker_entry.pack(pady=5)
        
        def create():
            files = [files_list.get(i) for i in files_list.curselection()]
            if not files:
                messagebox.showwarning("Warning", "No files selected")
                return
            tracker = tracker_entry.get()
            if not tracker:
                messagebox.showwarning("Warning", "No tracker URL")
                return
            save_path = filedialog.asksaveasfilename(defaultextension=".torrent")
            if save_path:
                try:
                    torrent_path = create_torrent_file(files, tracker, save_path)
                    time.sleep(0.5)
                    messagebox.showinfo("Success", f"Torrent created: {torrent_path}\nAdd it manually to start seeding.")
                    dialog.destroy()
                    self.status_bar.config(text="Torrent created")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create torrent: {e}")
        
        ttk.Button(dialog, text="Create", command=create).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)

    def select_torrent_file(self, torrent_path):
        base_path = filedialog.askdirectory(title="Select Download/Seed Location")
        if not base_path:
            messagebox.showwarning("Warning", "No location selected")
            return
        try:
            client = Client(torrent_path, base_path, port=6881)
            self.clients[torrent_path] = client
            self.paths[torrent_path] = base_path
            self.queue_list.insert(tk.END, os.path.basename(torrent_path))
            self.active_torrent = torrent_path
            self.torrent_file = torrent_path
            if client.check_file_exists():
                self.running = True
                self.start_btn.config(state=tk.DISABLED)
                self.pause_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.NORMAL)
                self.seed_thread = threading.Thread(target=client.listen_for_requests, daemon=False)
                self.seed_thread.start()
                self.event_queue.put(("state", "seeding"))
                self.status_bar.config(text="Seeding started")
            else:
                self.start_btn.config(state=tk.NORMAL)
            self.update_files_list()
        except Exception as e:
            logging.error(f"Failed to load torrent {torrent_path}: {e}")
            messagebox.showerror("Error", f"Failed to load torrent: {e}")

    def select_active_torrent(self, event):
        selection = self.queue_list.curselection()
        if selection:
            torrent = self.queue_list.get(selection[0])
            for path, client in self.clients.items():
                if os.path.basename(path) == torrent:
                    self.active_torrent = path
                    self.torrent_file = path
                    self.start_btn.config(state=tk.NORMAL if client.state == "stopped" else tk.DISABLED)
                    self.resume_btn.config(state=tk.NORMAL if client.state in ["paused", "stopped"] else tk.DISABLED)
                    self.pause_btn.config(state=tk.NORMAL if client.state in ["downloading", "seeding"] else tk.DISABLED)
                    self.stop_btn.config(state=tk.NORMAL if client.state in ["downloading", "seeding", "paused"] else tk.DISABLED)
                    self.update_files_list()
                    break

    def start_download(self):
        if not self.active_torrent or not self.clients.get(self.active_torrent):
            messagebox.showwarning("Warning", "No torrent selected")
            return
        client = self.clients[self.active_torrent]
        if client.check_file_exists():
            self.status_bar.config(text="Files already exist, seeding instead")
            return
        if self.download_thread and self.download_thread.is_alive():
            self.status_bar.config(text="Download already running")
            return
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_bar.config(text="Starting download...")
        self.download_thread = threading.Thread(target=client.start_download, daemon=False)
        self.download_thread.start()
        self.event_queue.put(("state", "downloading"))

    def resume_client(self):
        if not self.active_torrent or not self.clients.get(self.active_torrent):
            messagebox.showwarning("Warning", "No torrent selected")
            return
        client = self.clients[self.active_torrent]
        if client.state not in ["paused", "stopped"]:
            return
        self.running = True
        client.resume()
        self.resume_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_bar.config(text="Resuming...")
        if client.check_file_exists():
            self.seed_thread = threading.Thread(target=client.listen_for_requests, daemon=False)
            self.seed_thread.start()
            self.event_queue.put(("state", "seeding"))
        else:
            self.download_thread = threading.Thread(target=client.start_download, daemon=False)
            self.download_thread.start()
            self.event_queue.put(("state", "downloading"))

    def pause_client(self):
        if not self.active_torrent or not self.clients.get(self.active_torrent):
            return
        client = self.clients[self.active_torrent]
        client.pause()
        self.running = False
        self.resume_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.event_queue.put(("state", "paused"))
        self.status_bar.config(text="Paused")

    def stop_client(self):
        if not self.active_torrent or not self.clients.get(self.active_torrent):
            return
        client = self.clients[self.active_torrent]
        client.stop()
        self.running = False
        if self.download_thread and self.download_thread.is_alive():
            self.download_thread.join(timeout=5.0)
        if self.seed_thread and self.seed_thread.is_alive():
            self.seed_thread.join(timeout=5.0)
        self.download_thread = None
        self.seed_thread = None
        self.start_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except queue.Empty:
                break
        self.event_queue.put(("state", "stopped"))
        self.state_label.config(text="State: Stopped")
        self.speed_label.config(text="Speed: 0 KB/s")
        self.status_bar.config(text="Client stopped")
        self.clients[self.active_torrent] = Client(self.active_torrent, self.paths[self.active_torrent], port=6881)

    def open_file(self, file_path):
        try:
            os.startfile(file_path)
            self.status_bar.config(text=f"Opened {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")

    def open_folder(self):
        if not self.active_torrent or not self.clients.get(self.active_torrent):
            return
        base_path = self.paths.get(self.active_torrent)
        try:
            os.startfile(base_path)
            self.status_bar.config(text=f"Opened folder {base_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder: {e}")

    def open_selected_file(self):
        if not self.active_torrent:
            return
        item = self.files_tree.selection()
        if item:
            values = self.files_tree.item(item)["values"]
            if values[4] == "Open":
                file_path = os.path.join(self.paths[self.active_torrent], values[0])
                self.open_file(file_path)

    def kick_peer(self):
        if not self.active_torrent:
            return
        item = self.peers_tree.selection()
        if item:
            values = self.peers_tree.item(item)["values"]
            ip, port = values[0], values[1]
            client = self.clients[self.active_torrent]
            client.peers[:] = [p for p in client.peers if not (p["ip"] == ip and p["port"] == port)]
            self.status_bar.config(text=f"Kicked peer {ip}:{port}")

    def show_peer_menu(self, event):
        if self.peers_tree.selection():
            self.peer_menu.post(event.x_root, event.y_root)

    def show_file_menu(self, event):
        if self.files_tree.selection():
            self.file_menu.post(event.x_root, event.y_root)

    def update_files_list(self):
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        if self.active_torrent and self.clients.get(self.active_torrent):
            client = self.clients[self.active_torrent]
            base_path = self.paths.get(self.active_torrent, "")
            pieces_done = sum(client.piece_manager.have_pieces)
            total_pieces = client.piece_manager.total_pieces
            for file_info in client.metainfo["files"]:
                file_name = file_info["path"]
                file_path = os.path.join(base_path, file_name)
                size_mb = file_info["length"] / 1024 / 1024
                file_type = os.path.splitext(file_name)[1][1:].upper() or "Unknown"
                file_progress = (pieces_done / total_pieces * 100) if total_pieces > 0 else 0
                action = "Open" if os.path.exists(file_path) and client.piece_manager.all_pieces_downloaded() else ""
                self.files_tree.insert("", tk.END, values=(file_name, f"{size_mb:.2f}", file_type, f"{file_progress:.1f}%", action))

    def update_ui(self):
        try:
            if self.active_torrent and self.clients.get(self.active_torrent):
                client = self.clients[self.active_torrent]
                while not self.event_queue.empty():
                    event_type, value = self.event_queue.get_nowait()
                    if event_type == "state":
                        self.state_label.config(text=f"State: {value.capitalize()}")

                pieces_done = sum(client.piece_manager.have_pieces)
                total_pieces = client.piece_manager.total_pieces
                progress = (pieces_done / total_pieces * 100) if total_pieces > 0 else 0
                self.progress_bar["value"] = progress
                self.progress_label.config(text=f"Progress: {progress:.1f}%")
                
                peer_count = len(client.peers)
                if peer_count == 0 and client.get_speed(upload=True) > 0:
                    peer_count = sum(1 for pid, stats in client.peer_stats.items()
                                    if (time.time() - stats.last_update) < 60)
                self.peers_summary.config(text=f"Peers: {peer_count}")

                down_speed = client.get_speed(upload=False) if self.running else 0.0
                up_speed = client.get_speed(upload=True) if self.running else 0.0
                self.down_speeds.append(down_speed)
                self.up_speeds.append(up_speed)
                if len(self.down_speeds) > 5:
                    self.down_speeds.pop(0)
                    self.up_speeds.pop(0)
                avg_down = sum(self.down_speeds) / len(self.down_speeds) if self.down_speeds else 0.0
                avg_up = sum(self.up_speeds) / len(self.up_speeds) if self.up_speeds else 0.0
                self.speed_label.config(text=f"Down: {avg_down:.2f} KB/s | Up: {avg_up:.2f} KB/s")
                
                current_time = time.time()
                self.speed_history["download"].append(avg_down)
                self.speed_history["upload"].append(avg_up)
                self.time_history.append(current_time - self.time_history[0] if self.time_history else 0)
                if len(self.time_history) > 300:
                    self.speed_history["download"].pop(0)
                    self.speed_history["upload"].pop(0)
                    self.time_history.pop(0)
                self.ax.clear()
                self.ax.plot(self.time_history, self.speed_history["download"], label="Download", color="#4682B4")
                self.ax.plot(self.time_history, self.speed_history["upload"], label="Upload", color="#FFA500")
                self.ax.legend()
                self.ax.set_xlabel("Time (s)")
                self.ax.set_ylabel("Speed (KB/s)")
                self.ax.grid(True)
                self.ax.set_facecolor("#333333" if self.theme == "dark" else "#ffffff")
                self.fig.set_facecolor("#2e2e2e" if self.theme == "dark" else "#f0f0f0")
                self.canvas.draw()

                for item in self.peers_tree.get_children():
                    self.peers_tree.delete(item)
                for peer_id, stats in client.peer_stats.items():
                    self.peers_tree.insert("", tk.END, values=(
                        stats.ip, stats.port,
                        stats.pieces_downloaded, f"{stats.get_download_speed():.2f}",
                        stats.pieces_uploaded, f"{stats.get_upload_speed():.2f}"
                    ))

                self.update_files_list()
                self.status_bar.config(text="Running..." if self.running else "Idle")
            else:
                self.status_bar.config(text="Idle")
        except Exception as e:
            logging.error(f"UI update error: {e}")
            self.status_bar.config(text=f"Error: {e}")
        self.root.after(1000, self.update_ui)

    def files_tree_click(self, event):
        item = self.files_tree.selection()
        if item:
            values = self.files_tree.item(item)["values"]
            if values[4] == "Open":
                file_path = os.path.join(self.paths[self.active_torrent], values[0])
                self.open_file(file_path)

if __name__ == "__main__":
    root = tk.Tk()
    root.configure(bg="#2e2e2e")
    app = TorrentGUI(root)
    root.mainloop()