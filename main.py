import ctypes
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import yt_dlp as y
import sys
import socket
import json
from pathlib import Path


CONFIG_FILE = Path.home() / ".yt_downloader_config.json"

if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YourAppID.UniqueName")


def is_connected():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

def save_window_state():
    geometry = root.geometry()
    state_data = {
        "geometry": geometry
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(state_data, f)
    except Exception as e:
        print("Error saving window state:", e)

def load_window_state():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                state_data = json.load(f)
            geometry = state_data.get("geometry")
            if geometry:
                root.geometry(geometry)
        except Exception as e:
            print("Error loading window state:", e)

def resource_path(relative_path):
    """ Get absolute path to resources for both dev and PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    full_path = os.path.join(base_path, relative_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Resource not found: {full_path}")
    return full_path


# Placeholder text behavior
PLACEHOLDER_TEXT = "  Paste"

def add_placeholder(event=None):
    if not url_entry.get():
        url_entry.insert(0, PLACEHOLDER_TEXT)
        url_entry.config(fg="gray")

def remove_placeholder(event=None):
    if url_entry.get() == PLACEHOLDER_TEXT:
        url_entry.delete(0, tk.END)
        url_entry.config(fg="black")


window_closed_event = threading.Event()

def format_time(seconds):
    hours, rem = divmod(seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def update_gui(status, speed=None, eta=None, percentage=None):
    if window_closed_event.is_set():
        return
    status_label.config(text=status)
    if speed is not None:
        speed_label.config(text=f"Speed: {speed:.2f} MB/s")
    if eta is not None:
        eta_label.config(text=f"{format_time(eta)}")
    if percentage is not None:
        progress_bar['value'] = percentage
        percentage_label.config(text=f"{percentage:.1f}%")
        percentage_label.place(relx=0.5, rely=0.7, anchor="center") 
        root.update_idletasks()

def reset_gui():
    url_entry.config(state='normal')
    download_btn.pack()
    stop_btn.pack_forget()
    progress_bar.place_forget()
    speed_label.config(text="")
    eta_label.config(text="")
    percentage_label.config(text="")
    is_downloading.set(False)

def handle_download_error(error):
    error_msg = str(error).lower()
    if any(msg in error_msg for msg in ['unable to extract video data', 'unsupported url', 'invalid url']):
        display_msg = "Invalid or unsupported URL!"
    elif any(msg in error_msg for msg in [
        'unable to download webpage', 'connection', 'network', 'timed out',
        'failed to resolve', 'no internet', 'could not resolve host'
    ]):
        display_msg = "Network error! Please check your internet connection."
    else:
        display_msg = f"Error: {error}"
    messagebox.showerror("Error", display_msg)
    reset_gui()

def download_video():
    url = url_entry.get().strip()

    if not is_connected():
        messagebox.showerror("Network Error", "No internet connection. Please check your connection.")
        return

    if not url:
        messagebox.showwarning("Warning", "Please enter an URL.")
        return

    if url == PLACEHOLDER_TEXT:
        messagebox.showwarning("Warning", "Please enter an URL.")
        return

    # Simple YouTube URL validation
    youtube_pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    if not re.match(youtube_pattern, url):
        messagebox.showerror("Invalid URL", "Please enter a valid YouTube video URL.")
        return

    is_downloading.set(True)
    url_entry.config(state='disabled')
    download_btn.pack_forget()
    stop_btn.pack(pady=5)
    progress_bar['value'] = 0
    progress_bar.place(relx=0.42, rely=0.8, anchor="center")
    percentage_label.config(text="")
    update_gui("Fetching video info...")

    def fetch_info():
        try:
            with y.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'video')[:50]  # Limit title length
                ext = info.get('ext', 'mp4')
                root.after(0, lambda: show_save_dialog(url, f"{title}.{ext}"))
        except Exception as e:
            root.after(0, lambda: handle_download_error(e))

    threading.Thread(target=fetch_info, daemon=True).start()


def show_save_dialog(url, default_name):
    save_path = filedialog.asksaveasfilename(
        defaultextension=".mp4",
        initialfile=default_name,
        filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
    )
    if not save_path:
        reset_gui()
        return
    start_download(url, save_path)

def start_download(url, save_path):
    def run_download():
        try:
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
                'merge_output_format': 'mp4',
                'outtmpl': save_path,
                'progress_hooks': [progress_hook],
            }

            with y.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if not window_closed_event.is_set():
                root.after(0, lambda: update_gui("Download complete!"))
                messagebox.showinfo("Success", "Download completed successfully!")
        except Exception as e:
            if not window_closed_event.is_set():
                # FIX: Make sure `e` is in scope for the lambda
                root.after(0, lambda error=e: handle_download_error(error))
        finally:
            window_closed_event.clear()
            root.after(0, reset_gui)

    def progress_hook(d):
        if window_closed_event.is_set():
            sys.exit()
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes')
            speed = d.get('speed', 0)

            speed_mb = speed / (1024 * 1024) if speed else 0
            percentage = (downloaded_bytes / total_bytes * 100) if total_bytes else 0
            eta = d.get('eta', 0)

            root.after(0, lambda: update_gui(
                "Downloading...",
                speed=speed_mb,
                eta=eta,
                percentage=percentage
            ))

    download_thread = threading.Thread(target=run_download, daemon=True)
    download_thread.start()

def on_close():
    if messagebox.askokcancel("Quit", "Do you want to quit?"):
        save_window_state()
        window_closed_event.set()
        root.destroy()

def cancel_download():
    if messagebox.askokcancel("Cancel", "Do you want to cancel downloading?"):
        window_closed_event.set()


# GUI Setup
root = tk.Tk()
root.title("YouTube Video Downloader")
root.geometry("500x310")
root.resizable(False, False)
root.protocol("WM_DELETE_WINDOW", on_close)

try:
    root.iconbitmap(resource_path(r"icons/icon.ico"))
except Exception as e:
    print("Icon load error:", e) 
    
# Create Tkinter variables
is_downloading = tk.BooleanVar(value=False)

style = ttk.Style()
style.theme_use('clam')
style.configure("green.Horizontal.TProgressbar", 
                troughcolor='#e0e0e0',
                background='#28a745')

progress_bar = ttk.Progressbar(root, 
                              style="green.Horizontal.TProgressbar",
                              orient="horizontal",
                              mode="determinate",
                              length=400)
progress_bar.place(relx=0.42, rely=0.8, anchor="center")
progress_bar.place_forget()

# URL Entry with enhanced validation
tk.Label(root, text="Enter YouTube URL:", font=("Arial", 12)).pack(pady=10)
url_entry = tk.Entry(root, width=50, font=("Arial", 11, 'italic'), bg='#e0e0e0')
url_entry.pack(pady=5)

url_entry.insert(0, PLACEHOLDER_TEXT)
url_entry.config(fg="gray")

url_entry.bind("<FocusIn>", remove_placeholder)
url_entry.bind("<FocusOut>", add_placeholder)

def unfocus_on_click(event):
    widget = root.winfo_containing(event.x_root, event.y_root)
    if widget != url_entry:
        root.focus()

root.bind("<Button-1>", unfocus_on_click)

# Modified Enter key binding
def on_enter(event):
    if not is_downloading.get():
        download_video()
url_entry.bind('<Return>', on_enter)

# Buttons
download_btn = tk.Button(root, text="Download Video", font=("Arial", 11, "bold"),
                         command=download_video, bg="#28a745", fg="white")
download_btn.pack(pady=5)

stop_btn = tk.Button(root, text="Cancel Download", font=("Arial", 11, "bold"),
                    command=cancel_download, bg="red", fg="white")
stop_btn.pack_forget()

# Status labels
status_label = tk.Label(root, text="", font=("Arial", 11), fg="blue")
status_label.pack()

speed_label = tk.Label(root, text="", font=("Arial", 11))
speed_label.pack()

eta_label = tk.Label(root, text="", font=("Arial", 11))
eta_label.place(relx=0.9, rely=0.8, anchor="center")

percentage_label = tk.Label(root, text="", font=("Arial", 11))
percentage_label.place(relx=0.5, rely=0.7, anchor="center") 
percentage_label.place_forget()

load_window_state()

root.mainloop()