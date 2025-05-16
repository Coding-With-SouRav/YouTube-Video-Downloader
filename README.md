# YouTube Video Downloader Application 

---

**Overview**  
This Python-based GUI application allows users to download YouTube videos by providing a URL. It features a user-friendly interface, real-time download progress tracking, and basic error handling. The application is built with `tkinter` for the GUI and `yt-dlp` for backend video downloading.

---

**Key Features**  
1. **Intuitive GUI**  
   - Input field with placeholder text ("Paste")  
   - Progress bar with percentage completion  
   - Real-time download statistics (speed/ETA)  
   - Cancel download functionality  

2. **Core Functionality**  
   - YouTube URL validation using regex pattern  
   - Auto-fetch video title for default filename suggestions  
   - File save dialog with MP4 format prioritization  
   - Network connectivity check before downloads  

3. **Technical Implementation**  
   - Multi-threaded downloads to prevent GUI freezing  
   - Persistent window geometry configuration (saved to `~/.yt_downloader_config.json`)  
   - Cross-platform compatibility (Windows/Linux/macOS)  
   - PyInstaller-friendly resource handling via `resource_path()`  

4. **Error Handling**  
   - Network error detection  
   - Invalid URL/unsupported content warnings  
   - Graceful thread termination on cancellation  

---

**Dependencies**  
- `tkinter` (GUI framework)  
- `yt-dlp` (YouTube video/audio extraction)  
- `ctypes` (Windows taskbar integration)  
- `socket` (Internet connectivity check)  

---

**Workflow**  
1. User inputs YouTube URL  
2. Application validates URL format and internet connectivity  
3. Metadata extraction (video title, format)  
4. File save dialog appears with suggested filename  
5. Download starts with live progress updates:  
   - Speed (MB/s)  
   - Time remaining (HH:MM:SS)  
   - Progress bar + percentage  
6. Completed downloads trigger a success notification  

---

**Limitations & Potential Improvements**  
- **Current Limitations**:  
  - URL regex may miss some valid YouTube URLs (e.g., shortened links)  
  - No quality/format selection option  
  - Basic error messages could be more descriptive  

- **Enhancement Opportunities**:  
  - Add audio-only download option  
  - Implement playlist support  
  - Include resolution/bitrate selection  
  - Dark mode toggle  

---

**Usage Requirements**  
- Python 3.6+  
- Required packages: `yt-dlp`, `pyinstaller` (for bundling)  
- Internet connection for downloads  

---

**Screenshot of Key Components**  
*(Imagined visual elements)*  
- Central URL input field with placeholder text  
- Green "Download Video" button  
- Red "Cancel Download" button during active transfers  
- Progress bar with percentage overlay  
- Status labels for speed/ETA below the progress bar  

This application provides a streamlined experience for downloading YouTube content while maintaining essential user feedback and error resilience.
