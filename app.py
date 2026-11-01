import configparser
import ctypes
import http.client
import io
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.error
import urllib.request
import zipfile
from tkinter import filedialog
import winreg
import customtkinter as ctk
from PIL import Image, ImageOps

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp is missing. Run:  pip install yt-dlp")
if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "com.example.ytvideodownloader"
    )
BG = "#07080F"
PANEL = "#0C0E1B"
CYAN = "#1FF0FF"
SKY = "#3FA9FF"
BLUE_BORDER = "#2F6BFF"
BLUE_FIELD = "#0A1A55"
TEAL = "#19E6C8"
TEAL_FIELD = "#08171B"
PINK = "#FF3CC8"
PURPLE = "#A24BFF"
LAVENDER = "#8E8CFF"
LAV_TEXT = "#B79CFF"
VIOLET_FILL = "#9A2BFF"
VIOLET_HOVER = "#AE4BFF"
GREEN = "#2CFF6B"
GREEN_TEXT = "#6BFF8A"
GREEN_FIELD = "#07200F"
DANGER = "#FF4D6D"
TEXT = "#EDEBFF"
MUTED = "#8E92B5"
VIDEO_QUALITIES = [144, 240, 360, 480, 720, 1080, 1440, 2160]
AUDIO_BITRATES = [48, 64, 96, 128, 192, 256, 320]
THUMB_W, THUMB_H, THUMB_BORDER = (200, 150, 3)
THUMB_INNER_W = THUMB_W - 2 * THUMB_BORDER
THUMB_INNER_H = THUMB_H - 2 * THUMB_BORDER
SPIN_SIZE, SPIN_WIDTH = (46, 5)
SPIN_TAIL = "#0A2230"
MAX_URL_LEN = 2048
APP_DIR_NAME = "YoutubeDownloader"
FFMPEG_URL = (
    "https://github.com/Coding-With-SouRav/PACKAGES/releases/download/v1.0.0/ffmpeg.zip"
)
FFMPEG_EXE = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
NET_PROBES = [
    ("1.1.1.1", 443),
    ("8.8.8.8", 53),
    ("9.9.9.9", 443),
    ("www.youtube.com", 443),
]


class Cancelled(Exception):
    pass


def clean_error(err: Exception) -> str:
    text = re.sub("\\x1b\\[[0-9;]*m", "", str(err))
    text = text.replace("ERROR:", "").strip()
    return text[:160] + ("…" if len(text) > 160 else "")


def fmt_speed(bps):
    if not bps:
        return ""
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    i = 0
    while bps >= 1024 and i < len(units) - 1:
        bps /= 1024
        i += 1
    return f"{bps:.1f} {units[i]}"


def fmt_time(sec):
    if sec is None:
        return ""
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def has_internet(timeout=2.0):
    for host, port in NET_PROBES:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def locate_ffmpeg_bin(root):
    if not root or not os.path.isdir(root):
        return None
    for dirpath, _dirs, files in os.walk(root):
        if any((f.lower() == FFMPEG_EXE.lower() for f in files)):
            return dirpath
    return None


def prepend_to_process_path(folder):
    cur = os.environ.get("PATH", "")
    norm = lambda p: os.path.normcase(os.path.normpath(p))
    if norm(folder) not in [norm(p) for p in cur.split(os.pathsep) if p]:
        os.environ["PATH"] = folder + os.pathsep + cur


def add_to_windows_path(folder):
    prepend_to_process_path(folder)
    if sys.platform != "win32":
        return "none"

    def norm(p):
        return os.path.normcase(
            os.path.normpath(os.path.expandvars(p.strip().strip('"')))
        )

    def add(root, subkey):
        with winreg.OpenKey(
            root, subkey, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
        ) as key:
            try:
                current, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current, kind = ("", winreg.REG_EXPAND_SZ)
            parts = [p for p in current.split(";") if p.strip()]
            if norm(folder) not in {norm(p) for p in parts}:
                parts.append(folder)
                if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                    kind = winreg.REG_EXPAND_SZ
                winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts))

    scope = "none"
    for name, root, sub in (
        (
            "system",
            winreg.HKEY_LOCAL_MACHINE,
            "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
        ),
        ("user", winreg.HKEY_CURRENT_USER, "Environment"),
    ):
        try:
            add(root, sub)
            scope = name
            break
        except OSError:
            continue
    if scope != "none":
        try:
            result = ctypes.c_ulong()
            ctypes.windll.user32.SendMessageTimeoutW(
                65535, 26, 0, "Environment", 2, 5000, ctypes.byref(result)
            )
        except Exception:
            pass
    return scope


def find_ffmpeg(local_bin=None):
    if local_bin:
        exe = os.path.join(local_bin, FFMPEG_EXE)
        if os.path.isfile(exe):
            return exe
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def default_folder():
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    return d if os.path.isdir(d) else os.path.expanduser("~")


def pick_font(root):
    available = set(tkfont.families(root))
    for name in (
        "Orbitron",
        "Rajdhani",
        "Exo 2",
        "Audiowide",
        "Segoe UI",
        "SF Pro Display",
        "Noto Sans",
        "DejaVu Sans",
    ):
        if name in available:
            return name
    return "Helvetica"


def mix_black(hex_color: str, amount: float = 0.35) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    k = 1.0 - max(0.0, min(amount, 1.0))
    return "#%02X%02X%02X" % (int(r * k), int(g * k), int(b * k))


URL_RE = re.compile("https?://[^\\s<>\"\\'`]+", re.IGNORECASE)
YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
_TRAIL = ".,;:!?)]}'\""


def extract_url(text: str):
    if not text:
        return None
    text = text.strip()
    if not text:
        return None
    if (
        len(text) <= MAX_URL_LEN
        and (not any((c.isspace() for c in text)))
        and text[:8].lower().startswith(("https://", "http://"))
    ):
        return text.rstrip(_TRAIL)
    matches = [m.rstrip(_TRAIL) for m in URL_RE.findall(text)]
    if not matches:
        return None
    for m in matches:
        try:
            host = m.split("://", 1)[1].split("/", 1)[0]
            host = host.split("@")[-1].split(":")[0].lower()
        except IndexError:
            continue
        if host in YT_HOSTS and len(m) <= MAX_URL_LEN:
            return m
    for m in matches:
        if len(m) <= MAX_URL_LEN:
            return m
    return None


class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Fetchly")
        self.geometry("750x650")
        self.minsize(750, 650)
        self.configure(fg_color=BG)
        self.iconbitmap(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico"
            )
        )
        base = os.getenv("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
        self.config_dir = os.path.join(base, APP_DIR_NAME)
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "config.ini")
        self.q = queue.Queue()
        self.cancel_flag = threading.Event()
        self.busy = False
        self.fetching = False
        self.thumb_ref = None
        self.logo_ref = None
        self._spinner_on = False
        self._spin_angle = 0
        self._spin_job = None
        self.format_var = ctk.StringVar(value="mp4")
        self.folder_var = ctk.StringVar(value=self._load_save_path())
        self._save_job = None
        self.folder_var.trace_add("write", lambda *_: self._schedule_save_path())
        self.net_online = None
        self.net_event = threading.Event()
        self._closing = False
        self.ffmpeg_bin = locate_ffmpeg_bin(os.path.join(self.config_dir, "ffmpeg"))
        if self.ffmpeg_bin:
            prepend_to_process_path(self.ffmpeg_bin)
        self.setup_needed = sys.platform == "win32" and self.ffmpeg_bin is None
        self.setup_state = "idle"
        self._setup_frac = 0.0
        self._setup_stage = ""
        self._setup_detail = ""
        self._setup_error = ""
        self._ov_mode = None
        self.selected = {"mp4": 720, "mp3": 128}
        family = pick_font(self)
        self.f_logo = ctk.CTkFont(family, 42, "bold")
        self.f_tag = ctk.CTkFont(family, 16)
        self.f_label = ctk.CTkFont(family, 18)
        self.f_head = ctk.CTkFont(family, 17)
        self.f_body = ctk.CTkFont(family, 14)
        self.f_chip = ctk.CTkFont(family, 12, "bold")
        self.f_big = ctk.CTkFont(family, 18, "bold")
        self.f_dl = ctk.CTkFont(family, 30, "bold")
        self.f_title = ctk.CTkFont(family, 21)
        self.f_meta = ctk.CTkFont(family, 16)
        self.load_window_geometry()
        self._build()
        self._render_chips()
        self._apply_overlay()
        threading.Thread(target=self._net_monitor, daemon=True).start()
        self.after(80, self._poll)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _neon_button(
        self, parent, text, color, fill, width, command, height=40, hover_darken=0.35
    ):
        hover = mix_black(color, hover_darken)
        return ctk.CTkButton(
            parent,
            text=text,
            width=width,
            height=height,
            corner_radius=8,
            fg_color=fill,
            hover_color=hover,
            text_color=color,
            border_width=2,
            border_color=color,
            font=self.f_body,
            command=command,
        )

    def _panel(self, parent, title, border, title_color):
        frame = ctk.CTkFrame(
            parent,
            fg_color=PANEL,
            border_width=2,
            border_color=border,
            corner_radius=12,
        )
        label = ctk.CTkLabel(
            frame, text=title, font=self.f_head, text_color=title_color, anchor="w"
        )
        label.pack(fill="x", padx=14, pady=(8, 2))
        return (frame, label)

    def _build(self):
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=22, pady=18)
        root.grid_columnconfigure(0, weight=0)
        root.grid_columnconfigure(1, weight=1)
        head = ctk.CTkFrame(root, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        tab = ctk.CTkFrame(
            head, fg_color=PANEL, border_width=2, border_color=PURPLE, corner_radius=12
        )
        tab.pack(side="left")
        logo = ctk.CTkFrame(
            tab,
            width=58,
            height=58,
            fg_color="#10122A",
            border_width=2,
            border_color=PURPLE,
            corner_radius=10,
        )
        logo.pack(side="left", padx=(8, 1), pady=8)
        logo.pack_propagate(False)
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "assets", "f.png"
        )
        with Image.open(logo_path) as logo_image:
            logo_image = logo_image.convert("RGBA")
        self.logo_ref = ctk.CTkImage(
            light_image=logo_image, dark_image=logo_image, size=(42, 42)
        )
        ctk.CTkLabel(logo, text="", image=self.logo_ref).place(
            relx=0.5, rely=0.5, anchor="center"
        )
        ctk.CTkLabel(tab, text="etchly", font=self.f_logo, text_color=CYAN).pack(
            side="left", padx=(1, 20), pady=8
        )
        ctk.CTkLabel(
            head,
            text="Paste a link, pick a quality, save it.",
            font=self.f_tag,
            text_color=SKY,
        ).pack(side="left", padx=22)
        link = ctk.CTkFrame(root, fg_color="transparent")
        link.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(16, 14))
        link.grid_columnconfigure(1, weight=1)
        link_tag_frame = ctk.CTkFrame(
            link,
            fg_color="black",
            border_width=2,
            border_color=BLUE_BORDER,
            corner_radius=8,
        )
        link_tag_frame.grid(row=0, column=0, padx=(4, 14))
        ctk.CTkLabel(
            link_tag_frame, text="Video\nLink", font=self.f_label, text_color=SKY
        ).pack(padx=14, pady=6)
        self.url_entry = ctk.CTkEntry(
            link,
            height=42,
            corner_radius=8,
            border_width=2,
            border_color=BLUE_BORDER,
            fg_color=BLUE_FIELD,
            text_color="#FFFFFF",
            placeholder_text="https://www.youtube.com/watch?v=…",
            placeholder_text_color="#6F86C9",
            font=self.f_body,
        )
        self.url_entry.grid(row=0, column=1, sticky="ew")
        self.url_entry.bind("<Return>", lambda e: self.fetch_info())
        self.url_entry.bind("<<Paste>>", self._on_paste)
        self._neon_button(link, "Paste", TEAL, TEAL_FIELD, 100, self.paste_url).grid(
            row=0, column=2, padx=(12, 0)
        )
        self.fetch_btn = self._neon_button(
            link, "Preview", TEAL, TEAL_FIELD, 110, self.fetch_info
        )
        self.fetch_btn.grid(row=0, column=3, padx=(12, 0))
        left = ctk.CTkFrame(root, fg_color="transparent", width=THUMB_W + 20)
        left.grid(row=2, column=0, sticky="n", padx=(0, 18))
        thumb_frame = ctk.CTkFrame(
            left,
            fg_color="#000000",
            border_width=THUMB_BORDER,
            border_color=PINK,
            corner_radius=8,
            width=THUMB_W,
            height=THUMB_H,
        )
        thumb_frame.pack()
        thumb_frame.pack_propagate(False)
        self.thumb_text = ctk.CTkLabel(
            thumb_frame,
            text="Paste a link,\nthen press Preview",
            font=self.f_body,
            text_color=MUTED,
            fg_color="transparent",
            justify="center",
        )
        self.thumb_text.place(relx=0.5, rely=0.5, anchor="center")
        self.thumb_label = ctk.CTkLabel(
            thumb_frame,
            text="",
            fg_color="transparent",
            width=THUMB_INNER_W,
            height=THUMB_INNER_H,
        )
        self.spinner = tk.Canvas(
            thumb_frame,
            width=THUMB_INNER_W,
            height=THUMB_INNER_H,
            bg="#000000",
            highlightthickness=0,
            bd=0,
        )
        self.title_label = ctk.CTkLabel(
            left,
            text="",
            font=self.f_title,
            text_color=TEXT,
            justify="center",
            wraplength=THUMB_W,
        )
        self.title_label.pack(pady=(16, 2))
        self.meta_label = ctk.CTkLabel(
            left,
            text="",
            font=self.f_meta,
            text_color=MUTED,
            justify="center",
            wraplength=THUMB_W,
        )
        self.meta_label.pack()
        self.open_btn = self._neon_button(
            left, "Open folder", GREEN, GREEN_FIELD, 150, self.open_folder
        )
        right = ctk.CTkFrame(root, fg_color="transparent")
        right.grid(row=2, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(right, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        fmt_panel, _ = self._panel(top, "Format", PURPLE, LAV_TEXT)
        fmt_panel.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        for label, val in (("MP4", "mp4"), ("MP3", "mp3")):
            ctk.CTkRadioButton(
                fmt_panel,
                text=label,
                value=val,
                variable=self.format_var,
                font=self.f_label,
                text_color=TEXT,
                fg_color=VIOLET_FILL,
                hover_color=VIOLET_HOVER,
                border_color=LAVENDER,
                border_width_unchecked=2,
                border_width_checked=6,
                radiobutton_width=24,
                radiobutton_height=24,
                command=self._render_chips,
            ).pack(anchor="w", padx=(18, 10), pady=(6, 10))
        res_panel, self.quality_title = self._panel(top, "Resolution", PURPLE, LAV_TEXT)
        res_panel.grid(row=0, column=1, sticky="nsew")
        self.chip_frame = ctk.CTkFrame(res_panel, fg_color="transparent")
        self.chip_frame.pack(fill="x", padx=10, pady=(2, 10))
        for c in range(4):
            self.chip_frame.grid_columnconfigure(c, weight=1, uniform="chip")
        save_panel, _ = self._panel(right, "Save & Actions", GREEN, GREEN_TEXT)
        save_panel.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        srow = ctk.CTkFrame(save_panel, fg_color="transparent")
        srow.pack(fill="x", padx=14, pady=(4, 14))
        srow.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(srow, text="Save to", font=self.f_label, text_color=TEXT).grid(
            row=0, column=0, padx=(0, 12)
        )
        ctk.CTkEntry(
            srow,
            textvariable=self.folder_var,
            height=40,
            corner_radius=8,
            border_width=2,
            border_color=GREEN,
            fg_color=GREEN_FIELD,
            text_color="#FFFFFF",
            font=self.f_body,
        ).grid(row=0, column=1, sticky="ew")
        self._neon_button(
            srow, "Browse", GREEN, GREEN_FIELD, 100, self.choose_folder
        ).grid(row=0, column=2, padx=(12, 0))
        dl_outer = ctk.CTkFrame(
            right,
            fg_color="#150B33",
            border_width=2,
            border_color=PURPLE,
            corner_radius=16,
        )
        dl_outer.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        self.action_btn = ctk.CTkButton(
            dl_outer,
            text="Download",
            height=64,
            corner_radius=12,
            font=self.f_dl,
            fg_color="#5B2BD6",
            hover_color="#6F3BEE",
            text_color="#E3D6FF",
            border_width=2,
            border_color="#B68CFF",
            command=self._on_action,
        )
        self.action_btn.pack(fill="x", padx=8, pady=8)
        self.progress = ctk.CTkProgressBar(
            right,
            height=16,
            corner_radius=4,
            fg_color="#10101C",
            border_width=1,
            border_color="#3A2A66",
            progress_color="#09F448",
        )
        self.progress.set(0)
        self.progress.grid(row=3, column=0, sticky="ew", pady=(16, 6))
        info = ctk.CTkFrame(right, fg_color="transparent")
        info.grid(row=4, column=0, sticky="ew")
        self.status_label = ctk.CTkLabel(
            info,
            text="Ready",
            font=self.f_label,
            text_color=SKY,
            anchor="w",
            justify="left",
            wraplength=340,
        )
        self.status_label.pack(side="left")
        self.detail_label = ctk.CTkLabel(
            info, text="", font=self.f_body, text_color=CYAN, anchor="e"
        )
        self.detail_label.pack(side="right")
        self._build_overlay()

    def _show_thumb_image(self):
        if self.thumb_ref is not None:
            self.thumb_label.configure(image=self.thumb_ref, text="")
            self.thumb_label.place(relx=0.5, rely=0.5, anchor="center")
            self.thumb_text.place_forget()

    def _show_thumb_text(self, text):
        self.thumb_label.place_forget()
        self.thumb_text.configure(text=text)
        self.thumb_text.place(relx=0.5, rely=0.5, anchor="center")

    @staticmethod
    def _blend(c1, c2, t):
        a = tuple((int(c1[i : i + 2], 16) for i in (1, 3, 5)))
        b = tuple((int(c2[i : i + 2], 16) for i in (1, 3, 5)))
        return "#%02X%02X%02X" % tuple(
            (int(round(a[k] + (b[k] - a[k]) * t)) for k in range(3))
        )

    def _show_spinner(self):
        if self._spinner_on:
            return
        self._spinner_on = True
        self._spin_angle = 0
        self.thumb_text.place_forget()
        self.thumb_label.place_forget()
        self.spinner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Misc.tkraise(self.spinner)
        self._animate_spinner()

    def _hide_spinner(self):
        self._spinner_on = False
        if self._spin_job is not None:
            try:
                self.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None
        self.spinner.place_forget()
        self.spinner.delete("all")

    def _animate_spinner(self):
        if not self._spinner_on:
            return
        c = self.spinner
        c.delete("all")
        cx = THUMB_INNER_W / 2
        cy = THUMB_INNER_H / 2
        r = SPIN_SIZE / 2
        box = (cx - r, cy - r, cx + r, cy + r)
        c.create_oval(*box, outline="#122A33", width=SPIN_WIDTH)
        segs, ext = (7, 26)
        for i in reversed(range(segs)):
            color = self._blend(CYAN, SPIN_TAIL, i / segs)
            c.create_arc(
                *box,
                start=self._spin_angle - i * ext,
                extent=ext + 1,
                style="arc",
                outline=color,
                width=SPIN_WIDTH,
            )
        self._spin_angle = (self._spin_angle - 18) % 360
        self._spin_job = self.after(25, self._animate_spinner)

    def _render_chips(self):
        for w in self.chip_frame.winfo_children():
            w.destroy()
        fmt = self.format_var.get()
        is_video = fmt == "mp4"
        options = VIDEO_QUALITIES if is_video else AUDIO_BITRATES
        self.quality_title.configure(text="Resolution" if is_video else "Audio bitrate")
        for i, val in enumerate(options):
            sel = val == self.selected[fmt]
            label = f"{val}p" if is_video else f"{val} kbps"
            ctk.CTkButton(
                self.chip_frame,
                text=label,
                height=40,
                corner_radius=8,
                font=self.f_chip,
                fg_color=VIOLET_FILL if sel else PANEL,
                hover_color=VIOLET_HOVER if sel else "#1A1A38",
                text_color="#FFFFFF",
                border_width=2,
                border_color="#C58BFF" if sel else LAVENDER,
                command=lambda v=val: self._select_quality(v),
            ).grid(row=i // 4, column=i % 4, padx=5, pady=5, sticky="ew")

    def _select_quality(self, val):
        self.selected[self.format_var.get()] = val
        self._render_chips()

    def _on_paste(self, event=None):
        try:
            raw = self.clipboard_get()
        except Exception:
            return "break"
        url = extract_url(raw)
        if not url:
            if raw and len(raw) > 200:
                self._status("No link found in the pasted text.", DANGER)
            return "break"
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)
        if url != raw.strip():
            self._status("Link detected — press Preview.", SKY)
        return "break"

    def paste_url(self):
        try:
            raw = self.clipboard_get()
        except Exception:
            return
        url = extract_url(raw)
        if not url:
            self._status("No valid link found in clipboard.", DANGER)
            return
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)
        self.fetch_info()

    def choose_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self.folder_var.get(), title="Choose download folder"
        )
        if folder:
            self.folder_var.set(folder)

    def open_folder(self):
        folder = self.folder_var.get()
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    def _status(self, text, color=SKY):
        self.status_label.configure(text=text, text_color=color)

    def _on_action(self):
        if self.busy:
            self.cancel_flag.set()
            self._status("Cancelling…", SKY)
        else:
            self.start_download()

    def _set_busy(self, busy):
        self.busy = busy
        if busy:
            self.action_btn.configure(
                text="Cancel",
                fg_color="#B3203F",
                hover_color="#CF2D50",
                border_color="#FF8DA1",
                text_color="#FFE3E8",
            )
            self.open_btn.pack_forget()
        else:
            self.action_btn.configure(
                text="Download",
                fg_color="#5B2BD6",
                hover_color="#6F3BEE",
                border_color="#B68CFF",
                text_color="#E3D6FF",
            )

    def fetch_info(self):
        raw = self.url_entry.get()
        url = extract_url(raw)
        if not url:
            if raw.strip():
                self._status("That doesn't look like a valid link.", DANGER)
            return
        if url != raw:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            self._status("Link detected — looking up video…", SKY)
        if self.fetching:
            return
        self.fetching = True
        self.fetch_btn.configure(state="disabled", text="Loading…")
        self._status("Looking up video…", SKY)
        self.title_label.configure(text="")
        self.meta_label.configure(text="")
        self._show_spinner()
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url):
        try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "skip_download": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            thumb = None
            if info.get("thumbnail"):
                try:
                    req = urllib.request.Request(
                        info["thumbnail"], headers={"User-Agent": "Mozilla/5.0"}
                    )
                    thumb = urllib.request.urlopen(req, timeout=10).read()
                except Exception:
                    pass
            self.q.put(
                (
                    "info",
                    {
                        "title": info.get("title", "Untitled"),
                        "channel": info.get("uploader") or info.get("channel") or "",
                        "duration": info.get("duration"),
                    },
                    thumb,
                )
            )
        except Exception as e:
            self.q.put(("fetch_error", clean_error(e)))

    def start_download(self):
        raw = self.url_entry.get()
        url = extract_url(raw)
        if not url:
            self._status("Paste a valid video link first.", DANGER)
            return
        if url != raw:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
        folder = self.folder_var.get().strip()
        if not os.path.isdir(folder):
            self._status("That save folder doesn't exist. Choose another.", DANGER)
            return
        fmt = self.format_var.get()
        quality = self.selected[fmt]
        ffmpeg = find_ffmpeg(self.ffmpeg_bin)
        if fmt == "mp3" and (not ffmpeg):
            self._status("MP3 needs ffmpeg. Run: pip install imageio-ffmpeg", DANGER)
            return
        self.cancel_flag.clear()
        self._set_busy(True)
        self.progress.set(0)
        self.detail_label.configure(text="")
        self._status("Starting…", SKY)
        threading.Thread(
            target=self._download_worker,
            args=(url, folder, fmt, quality, ffmpeg),
            daemon=True,
        ).start()

    def _download_worker(self, url, folder, fmt, quality, ffmpeg):
        opts = {
            "outtmpl": os.path.join(folder, "%(title).150s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._pp_hook],
            "socket_timeout": 20,
            "retries": 3,
            "fragment_retries": 3,
        }
        if ffmpeg:
            opts["ffmpeg_location"] = ffmpeg
        if fmt == "mp4":
            if ffmpeg:
                h = quality
                opts["format"] = (
                    f"bestvideo[height<={h}][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/best[height<={h}]"
                )
                opts["merge_output_format"] = "mp4"
            else:
                opts["format"] = (
                    f"best[height<={quality}][ext=mp4]/best[height<={quality}]"
                )
                self.q.put(
                    (
                        "status",
                        "No ffmpeg: single-file video (max 720p). Run: pip install imageio-ffmpeg",
                        SKY,
                    )
                )
        else:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(quality),
                }
            ]
        while True:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                self.q.put(("done", folder))
                return
            except Exception as e:
                if self.cancel_flag.is_set() or isinstance(e, Cancelled):
                    self.q.put(("cancelled",))
                    return
                if not self.net_event.is_set() or not has_internet():
                    self.q.put(("status", "Waiting for internet connection…", SKY))
                    if not self._wait_online(honor_cancel=True):
                        self.q.put(("cancelled",))
                        return
                    self.q.put(("status", "Connection back — resuming…", SKY))
                    continue
                self.q.put(("error", clean_error(e)))
                return

    def _progress_hook(self, d):
        if self.cancel_flag.is_set():
            raise Cancelled()
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            frac = min(done / total, 1.0) if total else 0.0
            is_audio = d.get("info_dict", {}).get("vcodec") == "none"
            stage = "Downloading audio" if is_audio else "Downloading video"
            parts = [f"{frac * 100:.0f}%"]
            if d.get("speed"):
                parts.append(fmt_speed(d["speed"]))
            if d.get("eta") is not None:
                parts.append("ETA " + fmt_time(d["eta"]))
            self.q.put(("progress", frac, stage, "   ".join(parts)))

    def _pp_hook(self, d):
        if d["status"] == "started":
            self.q.put(("progress", 1.0, "Finishing up…", ""))

    def _poll(self):
        try:
            while True:
                self._handle(self.q.get_nowait())
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "progress":
            _, frac, stage, detail = msg
            self.progress.set(frac)
            self._status(stage, SKY)
            self.detail_label.configure(text=detail)
        elif kind == "status":
            self._status(msg[1], msg[2])
        elif kind == "done":
            self.progress.set(1)
            self.detail_label.configure(text="100%")
            self._status("Saved successfully", GREEN)
            self._set_busy(False)
            self.open_btn.pack(pady=(14, 0))
        elif kind == "cancelled":
            self.progress.set(0)
            self.detail_label.configure(text="")
            self._status("Download cancelled.", SKY)
            self._set_busy(False)
        elif kind == "error":
            self.progress.set(0)
            self.detail_label.configure(text="")
            self._status("Failed: " + msg[1], DANGER)
            self._set_busy(False)
        elif kind == "info":
            _, info, thumb = msg
            self.fetching = False
            self.fetch_btn.configure(state="normal", text="Preview")
            self.title_label.configure(text=info["title"])
            bits = [b for b in (info["channel"], fmt_time(info["duration"])) if b]
            self.meta_label.configure(text="   ".join(bits))
            loaded = False
            if thumb:
                try:
                    img = Image.open(io.BytesIO(thumb)).convert("RGB")
                    box = (THUMB_INNER_W * 2, THUMB_INNER_H * 2)
                    fitted = ImageOps.contain(img, box, method=Image.LANCZOS)
                    img = Image.new("RGB", box, (0, 0, 0))
                    img.paste(
                        fitted,
                        ((box[0] - fitted.width) // 2, (box[1] - fitted.height) // 2),
                    )
                    self.thumb_ref = ctk.CTkImage(
                        light_image=img,
                        dark_image=img,
                        size=(THUMB_INNER_W, THUMB_INNER_H),
                    )
                    self._show_thumb_image()
                    loaded = True
                except Exception:
                    loaded = False
            if not loaded:
                self._show_thumb_text("No preview available")
            self._hide_spinner()
            if not self.busy:
                self._status("Ready", SKY)
        elif kind == "fetch_error":
            self.fetching = False
            self.fetch_btn.configure(state="normal", text="Preview")
            self._show_thumb_text("Couldn't load\npreview")
            self._hide_spinner()
            self._status("Couldn't read that link: " + msg[1], DANGER)
        elif kind == "net":
            self.net_online = msg[1]
            if self.net_online and self.setup_needed and (self.setup_state == "idle"):
                self._start_ffmpeg_setup()
            self._apply_overlay()
        elif kind == "setup":
            _, self._setup_frac, self._setup_stage, self._setup_detail = msg
            self._apply_overlay()
        elif kind == "setup_done":
            _, bin_dir, scope = msg
            self.ffmpeg_bin = bin_dir
            self.setup_needed = False
            self.setup_state = "done"
            self._apply_overlay()
            if scope == "system":
                self._status("ffmpeg installed & added to system PATH", GREEN)
            elif scope == "user":
                self._status(
                    "ffmpeg installed (added to user PATH; run as Administrator for system PATH)",
                    SKY,
                )
            else:
                self._status("ffmpeg installed", GREEN)
        elif kind == "setup_error":
            self.setup_state = "error"
            self._setup_error = msg[1]
            self._apply_overlay()

    def _build_overlay(self):
        self.overlay = ctk.CTkFrame(self, fg_color=BG, corner_radius=0, border_width=0)
        box = ctk.CTkFrame(self.overlay, fg_color="transparent")
        box.place(relx=0.5, rely=0.5, anchor="center")
        self.ov_title = ctk.CTkLabel(box, text="", font=self.f_dl, text_color=SKY)
        self.ov_title.pack()
        self.ov_sub = ctk.CTkLabel(
            box,
            text="",
            font=self.f_body,
            text_color=MUTED,
            justify="center",
            wraplength=480,
        )
        self.ov_sub.pack(pady=(8, 0))
        self.ov_bar = ctk.CTkProgressBar(
            box,
            width=440,
            height=16,
            corner_radius=4,
            fg_color="#10101C",
            border_width=1,
            border_color="#3A2A66",
            progress_color="#09F448",
        )
        self.ov_bar.set(0)
        self.ov_detail = ctk.CTkLabel(box, text="", font=self.f_body, text_color=CYAN)
        self.ov_btns = ctk.CTkFrame(box, fg_color="transparent")
        self._neon_button(
            self.ov_btns, "Retry", TEAL, TEAL_FIELD, 110, self._retry_setup
        ).pack(side="left", padx=6)
        self._neon_button(
            self.ov_btns, "Skip", LAVENDER, PANEL, 110, self._skip_setup
        ).pack(side="left", padx=6)

    def _desired_overlay(self):
        if self.net_online is None:
            return "checking"
        if not self.net_online:
            return "offline"
        if self.setup_state == "running":
            return "setup"
        if self.setup_state == "error":
            return "error"
        return None

    def _apply_overlay(self):
        mode = self._desired_overlay()
        if mode == self._ov_mode:
            if mode == "setup":
                self._update_setup_widgets()
            return
        self._ov_mode = mode
        if mode is None:
            self.overlay.place_forget()
            return
        self.ov_bar.pack_forget()
        self.ov_detail.pack_forget()
        self.ov_btns.pack_forget()
        if mode == "checking":
            title, color, sub = ("Connecting…", SKY, "")
        elif mode == "offline":
            title, color = ("No internet connection", DANGER)
            sub = "Check your network. This screen goes away automatically once you're back online."
            if self.busy or self.setup_state == "running":
                sub += " Your download will resume by itself."
        elif mode == "setup":
            title, color, sub = ("Setting up ffmpeg", SKY, "")
        else:
            title, color = ("ffmpeg setup failed", DANGER)
            sub = self._setup_error
        self.ov_title.configure(text=title, text_color=color)
        self.ov_sub.configure(text=sub)
        if mode == "setup":
            self.ov_bar.pack(pady=(22, 0))
            self.ov_detail.pack(pady=(10, 0))
            self._update_setup_widgets()
        elif mode == "error":
            self.ov_btns.pack(pady=(20, 0))
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.overlay.tkraise()
        self.focus_set()

    def _update_setup_widgets(self):
        self.ov_bar.set(max(0.0, min(self._setup_frac, 1.0)))
        self.ov_sub.configure(text=self._setup_stage)
        self.ov_detail.configure(text=self._setup_detail)

    def _retry_setup(self):
        self._start_ffmpeg_setup()
        self._apply_overlay()

    def _skip_setup(self):
        self.setup_needed = False
        self.setup_state = "skipped"
        self._status("Continuing without the bundled ffmpeg.", SKY)
        self._apply_overlay()

    def _net_monitor(self):
        last = None
        while not self._closing:
            ok = has_internet()
            if ok:
                self.net_event.set()
            else:
                self.net_event.clear()
            if ok != last:
                last = ok
                self.q.put(("net", ok))
            time.sleep(1.5)

    def _wait_online(self, honor_cancel=False):
        while not self.net_event.wait(0.5):
            if self._closing:
                return False
            if honor_cancel and self.cancel_flag.is_set():
                return False
        return not self._closing

    def _start_ffmpeg_setup(self):
        self.setup_state = "running"
        self._setup_frac = 0.0
        self._setup_stage = "Preparing download…"
        self._setup_detail = ""
        threading.Thread(target=self._ffmpeg_worker, daemon=True).start()

    def _ffmpeg_worker(self):
        try:
            part = os.path.join(self.config_dir, "ffmpeg.zip.part")
            zpath = os.path.join(self.config_dir, "ffmpeg.zip")
            self._download_file(FFMPEG_URL, part)
            if not zipfile.is_zipfile(part):
                os.remove(part)
                raise RuntimeError("Downloaded file is not a valid zip archive.")
            os.replace(part, zpath)
            bin_dir = self._extract_ffmpeg(zpath)
            self.q.put(("setup", 0.99, "Adding ffmpeg to PATH…", ""))
            scope = add_to_windows_path(bin_dir)
            try:
                os.remove(zpath)
            except OSError:
                pass
            self.q.put(("setup", 1.0, "Done", "100%"))
            self.q.put(("setup_done", bin_dir, scope))
        except Exception as e:
            self.q.put(("setup_error", clean_error(e)))

    def _report_download(self, done, total, speed):
        frac = done / total if total else 0.0
        mb = 1024 * 1024
        parts = [f"{frac * 100:.0f}%" if total else ""]
        parts.append(
            f"{done / mb:.1f} / {total / mb:.1f} MB" if total else f"{done / mb:.1f} MB"
        )
        if speed:
            parts.append(fmt_speed(speed))
            if total:
                parts.append("ETA " + fmt_time((total - done) / speed))
        self.q.put(
            (
                "setup",
                0.9 * frac,
                "Downloading ffmpeg (one-time setup)…",
                "   ".join((p for p in parts if p)),
            )
        )

    def _download_file(self, url, dest):
        fails = 0
        speed = 0.0
        while True:
            if not self._wait_online():
                raise RuntimeError("Setup aborted.")
            offset = os.path.getsize(dest) if os.path.exists(dest) else 0
            headers = {"User-Agent": "Mozilla/5.0"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if offset and getattr(resp, "status", 200) != 206:
                        offset = 0
                    length = int(resp.headers.get("Content-Length") or 0)
                    total = offset + length if length else 0
                    done = offset
                    b_last, t_last = (done, time.monotonic())
                    self._report_download(done, total, 0)
                    with open(dest, "ab" if offset else "wb") as f:
                        while True:
                            chunk = resp.read(64 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                            done += len(chunk)
                            fails = 0
                            now = time.monotonic()
                            if now - t_last >= 0.1:
                                inst = (done - b_last) / (now - t_last)
                                speed = inst if not speed else speed * 0.7 + inst * 0.3
                                b_last, t_last = (done, now)
                                self._report_download(done, total, speed)
                if total and done < total:
                    raise ConnectionError("connection closed early")
                self._report_download(done, total, 0)
                return
            except urllib.error.HTTPError as e:
                if e.code == 416:
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                    continue
                if e.code < 500 and e.code not in (408, 429):
                    raise
                fails += 1
            except (urllib.error.URLError, OSError, http.client.HTTPException):
                fails += 1
            if self.net_event.is_set() and fails >= 6:
                raise RuntimeError("Download failed repeatedly. Try again.")
            time.sleep(1.5)

    def _extract_ffmpeg(self, zpath):
        tmp = os.path.join(self.config_dir, "_ffmpeg_tmp")
        final = os.path.join(self.config_dir, "ffmpeg")
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        root = os.path.abspath(tmp)
        with zipfile.ZipFile(zpath) as zf:
            infos = zf.infolist()
            total = sum((i.file_size for i in infos)) or 1
            done, t_last = (0, 0.0)
            for info in infos:
                target = os.path.abspath(os.path.join(root, info.filename))
                if os.path.commonpath([root, target]) != root:
                    continue
                if info.is_dir():
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    while True:
                        buf = src.read(256 * 1024)
                        if not buf:
                            break
                        dst.write(buf)
                        done += len(buf)
                        now = time.monotonic()
                        if now - t_last >= 0.1:
                            t_last = now
                            frac = done / total
                            self.q.put(
                                (
                                    "setup",
                                    0.9 + 0.09 * frac,
                                    "Extracting ffmpeg…",
                                    f"{frac * 100:.0f}%",
                                )
                            )
        src_bin = locate_ffmpeg_bin(tmp)
        if not src_bin:
            raise RuntimeError(f"{FFMPEG_EXE} was not found inside the archive.")
        shutil.rmtree(final, ignore_errors=True)
        if os.path.basename(src_bin).lower() == "bin":
            shutil.move(os.path.dirname(src_bin), final)
        else:
            os.makedirs(final)
            shutil.move(src_bin, os.path.join(final, "bin"))
        shutil.rmtree(tmp, ignore_errors=True)
        bin_dir = locate_ffmpeg_bin(final)
        if not bin_dir:
            raise RuntimeError("ffmpeg could not be installed.")
        return bin_dir

    def _read_config(self):
        cfg = configparser.ConfigParser(interpolation=None)
        try:
            cfg.read(self.config_file, encoding="utf-8")
        except (configparser.Error, OSError):
            pass
        return cfg

    def _write_config(self, section, values):
        cfg = self._read_config()
        if not cfg.has_section(section):
            cfg.add_section(section)
        for k, v in values.items():
            cfg.set(section, k, str(v))
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                cfg.write(f)
        except OSError:
            pass

    def _load_save_path(self):
        path = self._read_config().get("Settings", "save_path", fallback="").strip()
        return path if path and os.path.isdir(path) else default_folder()

    def _schedule_save_path(self):
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(500, self._save_path_now)

    def _save_path_now(self):
        self._save_job = None
        folder = self.folder_var.get().strip()
        if folder and os.path.isdir(folder):
            self._write_config("Settings", {"save_path": folder})

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
        self._write_config("Geometry", {"size": self.geometry(), "state": self.state()})

    def on_closing(self):
        self._closing = True
        self._save_path_now()
        self.save_window_geometry()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
