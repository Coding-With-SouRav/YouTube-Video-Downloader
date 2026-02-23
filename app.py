import configparser
import ctypes
from ctypes import wintypes
import sys
import customtkinter as ctk
from tkinter import filedialog
import threading
import os
import time
from yt_dlp import YoutubeDL
from PIL import Image
import tkinter as tk  # <-- added for Canvas

if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.example.ytvideodownloader")

username = os.getlogin()
FFMPEG_PATH = rf"C:\Users\{username}\AppData\Roaming\YoutubeDownloader\ffmpeg\bin\ffmpeg.exe"
FFMPEG_URL = "https://github.com/Coding-With-SouRav/PACKAGES/releases/download/v1.0.0/ffmpeg.zip"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    full_path = os.path.join(base_path, relative_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Resource not found: {full_path}")
    return full_path

def ensure_ffmpeg():
    """Check if ffmpeg.exe exists; if not, download and extract it with a premium progress window."""
    if os.path.exists(FFMPEG_PATH):
        return True

    import threading
    import urllib.request
    import zipfile
    import tempfile
    import shutil
    import customtkinter as ctk

    # Create a modern setup window
    root = ctk.CTk()
    root.title("FFmpeg Setup")
    
    # Window size
    window_width = 500
    window_height = 250

    # Get screen width and height
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Calculate position x, y
    x = int((screen_width / 2) - (window_width / 2))
    y = int((screen_height / 2) - (window_height / 2))

    # Set geometry
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    root.resizable(False, False)
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    # Widgets
    label = ctk.CTkLabel(root, text="FFmpeg not found. Downloading...", font=("Arial", 14))
    label.pack(pady=20)

    progress_bar = ctk.CTkProgressBar(root, width=400, height=15)
    progress_bar.pack(pady=10)
    progress_bar.set(0)

    size_label = ctk.CTkLabel(root, text="", font=("Arial", 12))
    size_label.pack(pady=5)

    # Cancellation event
    cancel_event = threading.Event()
    download_thread = None

    def on_closing():
        cancel_event.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # UI update helper (called from any thread via root.after)
    def update_progress(percent, downloaded_mb, total_mb, status="downloading", error_msg=""):
        if status == "downloading":
            progress_bar.set(percent / 100)
            if total_mb > 0:
                size_label.configure(text=f"Downloaded: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({percent:.1f}%)")
            else:
                size_label.configure(text=f"Downloaded: {downloaded_mb:.1f} MB")
        elif status == "extracting":
            label.configure(text="Extracting...")
            progress_bar.configure(mode="indeterminate")
            progress_bar.start()
            size_label.configure(text="")
        elif status == "complete":
            progress_bar.stop()
            progress_bar.configure(mode="determinate")
            progress_bar.set(1.0)
            label.configure(text="FFmpeg setup complete!")
            size_label.configure(text="")
            root.after(1500, root.destroy)  # Auto‑close after success
        elif status == "error":
            progress_bar.stop()
            label.configure(text=f"Error: {error_msg}")
            size_label.configure(text="")
            root.after(3000, root.destroy)

    def download_ffmpeg():
        target_dir = os.path.dirname(os.path.dirname(FFMPEG_PATH))
        os.makedirs(target_dir, exist_ok=True)

        zip_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        zip_path = zip_temp.name
        zip_temp.close()

        try:
            # Download with live progress
            def reporthook(blocknum, blocksize, totalsize):
                if cancel_event.is_set():
                    raise Exception("Download cancelled")
                downloaded = blocknum * blocksize
                if totalsize > 0:
                    percent = downloaded / totalsize * 100
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = totalsize / (1024 * 1024)
                    root.after(0, update_progress, percent, downloaded_mb, total_mb, "downloading")
                else:
                    downloaded_mb = downloaded / (1024 * 1024)
                    root.after(0, update_progress, 0, downloaded_mb, 0, "downloading")

            urllib.request.urlretrieve(FFMPEG_URL, zip_path, reporthook)

            if cancel_event.is_set():
                raise Exception("Download cancelled")

            # Switch to extraction mode
            root.after(0, update_progress, 0, 0, 0, "extracting")

            # Extract zip
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)

            # Flatten the extracted folder (GitHub release often has a top‑level folder)
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                if os.path.isdir(item_path):
                    for content in os.listdir(item_path):
                        src = os.path.join(item_path, content)
                        dst = os.path.join(target_dir, content)
                        if os.path.exists(dst):
                            if os.path.isdir(dst):
                                shutil.rmtree(dst)
                            else:
                                os.remove(dst)
                        shutil.move(src, dst)
                    os.rmdir(item_path)
                    break

            if cancel_event.is_set():
                raise Exception("Download cancelled")

            root.after(0, update_progress, 0, 0, 0, "complete")

        except Exception as e:
            if not cancel_event.is_set():
                error_msg = str(e)
                root.after(0, lambda: update_progress(0, 0, 0, "error", error_msg))
            else:
                root.after(0, root.destroy)
        finally:
            if os.path.exists(zip_path):
                os.unlink(zip_path)

    download_thread = threading.Thread(target=download_ffmpeg, daemon=True)
    download_thread.start()

    root.mainloop()

    # After window closes, verify FFmpeg is present
    if not os.path.exists(FFMPEG_PATH):
        ctypes.windll.user32.MessageBoxW(0, "FFmpeg setup failed. Please install manually.", "Error", 0)
        sys.exit(1)
    return True


class WindowIconSetter:
    def __init__(self, window_title, icon_path):
        self.window_title = window_title
        self.icon_path = os.path.abspath(icon_path) if icon_path else None
        
        self.user32 = ctypes.windll.user32
        self.shell32 = ctypes.windll.shell32
        
    def find_window_by_title(self, title):
        hwnd = self.user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
        
        windows = []
        
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_windows_callback(hwnd, lParam):
            length = self.user32.GetWindowTextLengthW(hwnd) + 1
            buffer = ctypes.create_unicode_buffer(length)
            self.user32.GetWindowTextW(hwnd, buffer, length)
            
            if title in buffer.value:
                windows.append(hwnd)
            return True
        
        self.user32.EnumWindows(enum_windows_callback, 0)
        
        if windows:
            return windows[0]
        
        return None
    
    def set_icon(self):
        if not self.icon_path or not os.path.exists(self.icon_path):
            print(f"Icon file not found: {self.icon_path}")
            return False
        
        hwnd = None
        for i in range(50):
            hwnd = self.find_window_by_title(self.window_title)
            if hwnd:
                break
            time.sleep(0.1)
        
        if not hwnd:
            print(f"Window '{self.window_title}' not found")
            return False
        
        try:
            LR_LOADFROMFILE = 0x10
            IMAGE_ICON = 1
            
            hicon_small = self.user32.LoadImageW(
                0,
                self.icon_path,
                IMAGE_ICON,
                16, 16,
                LR_LOADFROMFILE
            )
            
            hicon_large = self.user32.LoadImageW(
                0,
                self.icon_path,
                IMAGE_ICON,
                32, 32,
                LR_LOADFROMFILE
            )
            
            WM_SETICON = 0x80
            ICON_SMALL = 0
            ICON_BIG = 1
            
            if hicon_small:
                self.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
            
            if hicon_large:
                self.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_large)
            
            return True
            
        except Exception as e:
            print(f"Error setting icon: {e}")
            return False

class SilentLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Downloader")
        self.geometry("720x640")
        self.iconbitmap(resource_path(r"assets/icon.ico"))
        self.minsize(600, 640)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.download_thread = None
        self.cancel_event = None
        self.current_folder = None
        self.after_id = None
        self.download_active = False
        self.video_quality_text = "🎬 MP4"
        self.audio_quality_text = "🎵 MP3"
        config_dir = os.path.join(os.getenv('APPDATA'), "YoutubeDownloader")
        os.makedirs(config_dir, exist_ok=True)
        self.config_file = os.path.join(config_dir, 'config.ini')

        self.load_window_geometry()
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Arrow animation control
        self.arrow_animation_running = False
        self.arrow_after_id = None

    def create_widgets(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=30, pady=30)

        title = ctk.CTkLabel(
            main, text="YouTube Downloader",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        title.pack(pady=(0, 10))

        yt_img = Image.open(resource_path(r"assets\youtube.png")).resize((32, 32))
        ctk_image = ctk.CTkImage(
            light_image=yt_img,
            dark_image=yt_img,
            size=(40,40)
        )
        label = ctk.CTkLabel(main, image=ctk_image, text="")
        label.pack(pady=(10,0))
        label.image = ctk_image

        url_frame = ctk.CTkFrame(main, fg_color="transparent")
        url_frame.pack(fill="x", pady=(0, 15))

        url_label = ctk.CTkLabel(
            url_frame, text="VIDEO LINK",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#d6e4ff"
        )
        url_label.pack(anchor="w")

        self.url_entry = ctk.CTkEntry(
            url_frame, placeholder_text="  Paste YouTube URL here",
            height=45, font=ctk.CTkFont(size=15)
        )
        self.url_entry.pack(fill="x", pady=(5, 0))
        self.url_entry.bind("<KeyRelease>", self.on_url_change)
        self.url_entry.bind("<<Paste>>", self.on_url_paste)

        format_frame = ctk.CTkFrame(main, fg_color="transparent")
        format_frame.pack(fill="x", pady=15)

        self.format_var = ctk.StringVar(value="video")
        self.video_radio = ctk.CTkRadioButton(
            format_frame, text=self.video_quality_text,
            variable=self.format_var, value="video",
            font=ctk.CTkFont(size=15)
        )
        self.video_radio.pack(anchor="w", pady=5)

        self.audio_radio = ctk.CTkRadioButton(
            format_frame, text=self.audio_quality_text,
            variable=self.format_var, value="audio",
            font=ctk.CTkFont(size=15)
        )
        self.audio_radio.pack(anchor="w", pady=5)

        self.action_btn = ctk.CTkButton(
            main, text="DOWNLOAD NOW",
            command=self.start_download,
            height=50, font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#3068e0", hover_color="#4078f0"
        )
        self.action_btn.pack(fill="x", pady=20)

        self.progress_frame = ctk.CTkFrame(main, fg_color="#1a1f30", corner_radius=20)
        self.progress_frame.pack(fill="x", pady=(0, 15))
        self.progress_frame.pack_forget()

        # Header with animated arrow and status badge
        header = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))

        # Canvas for animated arrow
        self.arrow_canvas = tk.Canvas(
            header, width=40, height=40,
            bg="#1a1f30", highlightthickness=0, bd=0
        )
        self.arrow_canvas.pack(side="left", padx=(0, 5))
        self.arrow_item = self.arrow_canvas.create_text(
            20, 20, text="⬇", font=("Arial", 20), fill="cyan", anchor="center"
        )

        self.status_badge = ctk.CTkLabel(
            header, text="Downloading",  # removed arrow emoji
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#aae6ff"
        )
        self.status_badge.pack(side="left")

        self.percent_display = ctk.CTkLabel(
            header, text="0%",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="white"
        )
        self.percent_display.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=12, corner_radius=10)
        self.progress_bar.pack(fill="x", padx=20, pady=10)
        self.progress_bar.set(0)

        stats = ctk.CTkFrame(self.progress_frame, fg_color="#0f121c", corner_radius=15)
        stats.pack(fill="x", padx=20, pady=(0, 15))

        self.downloaded_label = ctk.CTkLabel(stats, text="0MB / ?MB", font=ctk.CTkFont(size=13))
        self.downloaded_label.pack(side="left", padx=15, pady=8)

        self.speed_label = ctk.CTkLabel(stats, text="?B/s", font=ctk.CTkFont(size=13))
        self.speed_label.pack(side="left", padx=15, pady=8)

        self.eta_label = ctk.CTkLabel(stats, text="?s", font=ctk.CTkFont(size=13))
        self.eta_label.pack(side="left", padx=15, pady=8)

        self.status_label = ctk.CTkLabel(
            main, text="⚡ Ready – you'll pick the save folder before download.",
            justify="left", anchor="w",
            fg_color="#0a0d14", corner_radius=15,
            padx=20, pady=15
        )
        self.status_label.pack(fill="x", pady=(0, 10))

    # Arrow animation methods
    def animate_arrow(self):
        if not self.arrow_animation_running:
            return
        self.arrow_canvas.move(self.arrow_item, 0, 5)
        x, y = self.arrow_canvas.coords(self.arrow_item)
        if y > 40:  # canvas height
            self.arrow_canvas.coords(self.arrow_item, 20, 0)
        self.arrow_after_id = self.after(50, self.animate_arrow)

    def start_arrow_animation(self):
        if not self.arrow_animation_running:
            self.arrow_animation_running = True
            self.animate_arrow()

    def stop_arrow_animation(self):
        self.arrow_animation_running = False
        if self.arrow_after_id:
            self.after_cancel(self.arrow_after_id)
            self.arrow_after_id = None
        # Reset arrow position
        self.arrow_canvas.coords(self.arrow_item, 20, 00)

    # ... (all other methods unchanged from original, except where noted) ...

    def on_url_change(self, event=None):
        self.schedule_fetch_info()

    def on_url_paste(self, event=None):
        self.after(100, self.schedule_fetch_info)

    def schedule_fetch_info(self):
        if self.after_id:
            self.after_cancel(self.after_id)
        url = self.url_entry.get().strip()
        if url:
            self.after_id = self.after(500, self.fetch_info_thread, url)
        else:
            self.video_quality_text = "🎬 MP4"
            self.audio_quality_text = "🎵 MP3"
            self.update_radio_labels()

    def fetch_info_thread(self, url):
        threading.Thread(target=self._fetch_info, args=(url,), daemon=True).start()

    def _fetch_info(self, url):
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'logger': SilentLogger(),
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
            if FFMPEG_PATH:
                ydl_opts['ffmpeg_location'] = FFMPEG_PATH
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                video_formats = [f for f in formats if f.get('vcodec') != 'none']
                resolution_label = 'N/A'
                if video_formats:
                    best_video = max(video_formats, key=lambda f: f.get('height', 0))
                    height = best_video.get('height', 0)
                    if height >= 2160:
                        resolution_label = '4K (2160p)'
                    elif height >= 1440:
                        resolution_label = '2K (1440p)'
                    elif height >= 1080:
                        resolution_label = '1080p'
                    elif height >= 720:
                        resolution_label = '720p'
                    elif height >= 480:
                        resolution_label = '480p'
                    elif height >= 360:
                        resolution_label = '360p'
                    else:
                        resolution_label = f'{height}p' if height else 'N/A'
                audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                bitrate_label = 'N/A'
                if audio_formats:
                    best_audio = max(audio_formats, key=lambda f: f.get('abr', 0) or f.get('tbr', 0))
                    bitrate = best_audio.get('abr', 0) or best_audio.get('tbr', 0)
                    bitrate_label = f'{int(bitrate)}kbps' if bitrate else 'N/A'
                else:
                    any_audio = [f for f in formats if f.get('acodec') != 'none']
                    if any_audio:
                        best_any = max(any_audio, key=lambda f: f.get('abr', 0) or f.get('tbr', 0))
                        bitrate = best_any.get('abr', 0) or best_any.get('tbr', 0)
                        bitrate_label = f'{int(bitrate)}kbps' if bitrate else 'N/A'
                self.after(0, self._update_quality_labels, resolution_label, bitrate_label)
        except Exception:
            pass

    def _update_quality_labels(self, video_qual, audio_qual):
        if video_qual != 'N/A':
            self.video_quality_text = f"🎬 MP4 · {video_qual}"
        else:
            self.video_quality_text = "🎬 MP4"
        if audio_qual != 'N/A':
            self.audio_quality_text = f"🎵 MP3 · {audio_qual}"
        else:
            self.audio_quality_text = "🎵 MP3"
        self.update_radio_labels()

    def update_radio_labels(self):
        self.video_radio.configure(text=self.video_quality_text)
        self.audio_radio.configure(text=self.audio_quality_text)

    def set_arrow_symbol(self, symbol):
        """Change the arrow canvas text to the given symbol."""
        self.arrow_canvas.itemconfig(self.arrow_item, text=symbol)

    def start_download(self):
        if self.download_active:
            return
        url = self.url_entry.get().strip()
        if not url:
            self.update_status("❌ Please enter a YouTube URL.", is_error=True)
            return
        folder = filedialog.askdirectory(title="Select folder to save download")
        if not folder:
            self.update_status("⏹️ No folder selected. Download cancelled.")
            return
        self.current_folder = folder
        self.update_status(f"📁 Selected: {os.path.basename(folder)}")
        self.download_active = True
        self.action_btn.configure(
            text="CANCEL DOWNLOAD",
            command=self.cancel_download,
            fg_color="#c0394b", hover_color="#d44c5e"
        )
        self.url_entry.configure(state="disabled")
        self.video_radio.configure(state="disabled")
        self.audio_radio.configure(state="disabled")
        self.progress_frame.pack(fill="x", pady=(0, 15), before=self.status_label)
        self.progress_bar.set(0)
        self.percent_display.configure(text="0%")
        self.status_badge.configure(text="⏳ Preparing")
        # Set hourglass and stop arrow animation
        self.set_arrow_symbol("")
        self.stop_arrow_animation()
        self.cancel_event = threading.Event()
        self.download_thread = threading.Thread(
            target=self._download_thread,
            args=(url, self.format_var.get(), folder, self.cancel_event),
            daemon=True
        )
        self.download_thread.start()

    def cancel_download(self):
        if self.cancel_event:
            self.cancel_event.set()
            self.update_status("⏹️ Cancelling download...")
            self.action_btn.configure(state="disabled")
            self.stop_arrow_animation()

    def _download_thread(self, url, option, dest_dir, cancel_event):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(dest_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'logger': SilentLogger(),
                'progress_hooks': [self._progress_hook],
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            }
            if FFMPEG_PATH:
                ydl_opts['ffmpeg_location'] = FFMPEG_PATH
            if option == 'video':
                ydl_opts.update({
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'merge_output_format': 'mp4',
                })
            else:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            with YoutubeDL(ydl_opts) as ydl:
                self.after(0, self.update_status, "Fetching video info...")
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown Title')
                self.after(0, self.update_status, f"Downloading: {title}")
                ydl.download([url])
                if cancel_event.is_set():
                    return
                self.after(0, self._download_complete, dest_dir)
        except Exception as e:
            if cancel_event and cancel_event.is_set():
                self.after(0, self._download_cancelled)
            else:
                self.after(0, self._download_error, str(e))

    _last_progress_update = 0

    def _progress_hook(self, d):
        if self.cancel_event and self.cancel_event.is_set():
            raise Exception("Download cancelled by user")
        if d['status'] == 'downloading':
            now = time.time()
            if now - self._last_progress_update < 0.2:
                return
            self._last_progress_update = now
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total > 0:
                percent = downloaded / total * 100
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)

                def format_bytes(b):
                    if b < 1024:
                        return f"{b}B"
                    elif b < 1024**2:
                        return f"{b/1024:.1f}KB"
                    elif b < 1024**3:
                        return f"{b/1024**2:.1f}MB"
                    else:
                        return f"{b/1024**3:.2f}GB"
                downloaded_str = format_bytes(downloaded)
                total_str = format_bytes(total)
                speed_str = format_bytes(speed) + "/s" if speed else "?B/s"
                eta_str = f"{eta}s" if eta else "?s"
                self.after(0, self._update_progress_ui, {
                    "percent": round(percent, 1),
                    "downloaded": downloaded_str,
                    "total": total_str,
                    "speed": speed_str,
                    "eta": eta_str,
                    "status": "downloading"
                })
        elif d['status'] == 'finished':
            self.after(0, self._update_progress_ui, {"status": "processing", "percent": 100})

    def _update_progress_ui(self, data):
        if data.get("status") == "downloading":
            self.progress_bar.set(data["percent"] / 100)
            self.percent_display.configure(text=f"{data['percent']}%")
            self.downloaded_label.configure(text=f"{data['downloaded']} / {data['total']}")
            self.speed_label.configure(text=data["speed"])
            self.eta_label.configure(text=data["eta"])
            self.status_badge.configure(text="Downloading")
            # Switch to arrow and start animation
            self.set_arrow_symbol("⬇")
            self.start_arrow_animation()
        elif data.get("status") == "processing":
            self.status_badge.configure(text="⌛ Processing")
            self.progress_bar.set(1.0)
            self.percent_display.configure(text="100%")
            self.stop_arrow_animation()   # <-- start animation
        elif data.get("status") == "processing":
            self.status_badge.configure(text=" ⌛ Processing")
            self.progress_bar.set(1.0)
            self.percent_display.configure(text="100%")
            self.stop_arrow_animation()    # <-- stop animation
        elif data.get("status") == "complete":
            self._download_complete(None)
        elif data.get("status") == "cancelled":
            self._download_cancelled()
        elif data.get("status") == "error":
            self._download_error("Unknown error")

    def _download_complete(self, folder):
        self.stop_arrow_animation()
        self.reset_ui()
        self.update_status(f"✅ Download complete! Saved to: {folder}")

    def _download_cancelled(self):
        self.stop_arrow_animation()
        self.reset_ui()
        self.update_status("⏹️ Download cancelled.")
        self.progress_frame.pack_forget()

    def _download_error(self, error_msg):
        self.stop_arrow_animation()
        self.reset_ui()
        self.update_status(f"❌ Error: {error_msg}", is_error=True)
        self.progress_frame.pack_forget()

    def reset_ui(self):
        self.download_active = False
        self.cancel_event = None
        self.action_btn.configure(
            text="DOWNLOAD NOW",
            command=self.start_download,
            fg_color="#3068e0", hover_color="#4078f0",
            state="normal"
        )
        self.url_entry.configure(state="normal")
        self.video_radio.configure(state="normal")
        self.audio_radio.configure(state="normal")
        self.progress_frame.pack_forget()
        # Reset arrow symbol and stop animation
        self.set_arrow_symbol("⬇")
        self.stop_arrow_animation()   # ensure arrow stopped

    def update_status(self, message, is_error=False):
        color = "#ff9999" if is_error else "#ecf3ff"
        self.status_label.configure(text=message, text_color=color)

    def load_window_geometry(self):
        if os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config.read(self.config_file)
            if "Geometry" in config:
                geometry = config["Geometry"].get("size", "")
                state = config["Geometry"].get("state", "normal")
                if geometry:
                    self.geometry(geometry)
                    self.update_idletasks()
                    self.update()
                if state == "zoomed":
                    self.state("zoomed")
                elif state == "iconic":
                    self.iconify()

    def save_window_geometry(self):
        config = configparser.ConfigParser()
        config["Geometry"] = {
            "size": self.geometry(),
            "state": self.state()
        }
        with open(self.config_file, "w") as f:
            config.write(f)
    
    def on_closing(self):
        self.save_window_geometry()
        self.destroy()

if __name__ == "__main__":
    ensure_ffmpeg()
    app = App()
    icon_path = resource_path(r"assets/icon.ico")
    icon_setter = WindowIconSetter("YouTube Downloader", icon_path)
    def apply_icon_async():
        time.sleep(1)
        icon_setter.set_icon()
    threading.Thread(target=apply_icon_async, daemon=True).start()
    app.mainloop()