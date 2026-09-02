import sys
import os
import uuid
import ffmpeg
import subprocess
import json
import threading
import time
from functools import partial

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QPoint, QPropertyAnimation, QEvent, QEasingCurve, pyqtSignal, QObject, QRectF, QThread, QElapsedTimer
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSlider, QWidget, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QLabel, QSizePolicy, QMenu, QToolButton, QScrollArea,
    QStyle, QCheckBox, QDialog, QListWidget, QStackedWidget, QFormLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QGroupBox, QMessageBox,
    QProgressDialog
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QShortcut, QCursor
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

# Name used for the single-instance IPC channel (see __main__).
SINGLE_INSTANCE_KEY = "CrustyMediaPlayer_SingleInstance"
APP_VERSION = "1.4.4"


def running_on_wayland():
    """True when Qt is using the Wayland platform plugin (not XWayland/xcb).

    Used to work around a Qt 6 bug: resizing this frameless top-level window
    after a video is loaded (see on_extraction_finished) permanently breaks
    QVideoWidget's video scaling on Wayland - the video renders far larger
    than the widget and is clipped, until the window is manually moved or
    resized. Under a tiling compositor (Hyprland, Sway) the compositor
    rejects the resize outright, so the auto-fit is useless there anyway.
    On X11, Windows and macOS the resize works fine and is kept.
    """
    if os.name == "nt" or sys.platform == "darwin":
        return False
    try:
        name = QApplication.platformName()
        if name:
            return name.lower().startswith("wayland")
    except Exception:
        pass
    if os.environ.get("WAYLAND_DISPLAY"):
        return os.environ.get("XDG_SESSION_TYPE", "").lower() != "x11"
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"

# ----------------------------- Settings & Themes ----------------------------- #

def get_settings():
    app_name = "CrustyMediaPlayer"
    if os.name == "nt":
        base = os.getenv("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    settings_dir = os.path.join(base, app_name)
    os.makedirs(settings_dir, exist_ok=True)
    return os.path.join(settings_dir, "settings.json")

SETTINGS_FILE = get_settings()

def load_settings():
    """Load all settings from file"""
    default_settings = {
        "theme": "dark",
        "slider_orientation": "horizontal",
        "remember_volumes": False,
        "saved_volumes": {},
        "fullscreen_on_start": False,
        "auto_hide_controls": True,
        "hide_delay": 2000,
        # 0 = disabled, else px from bottom edge to reveal controls
        "mouse_reveal_zone": 60,
        "recent_files": [],
        "last_open_dir": "",
        "max_volume": 400,  # percent, default 400%
        "audio_cache_limit_mb": 2000  # cap for AUDIO_CACHE_DIR; oldest files pruned when exceeded
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                loaded = json.load(f)
                default_settings.update(loaded)
                # Guard against a corrupted/hand-edited file: max_volume feeds
                # a division elsewhere and must never be <= 0.
                try:
                    default_settings["max_volume"] = max(1, min(1000, int(default_settings.get("max_volume", 400))))
                except (TypeError, ValueError):
                    default_settings["max_volume"] = 400
                return default_settings
        except Exception:
            pass
    return default_settings

def save_settings(settings):
    """Save all settings to file"""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

def load_theme():
    return load_settings().get("theme", "dark")

DARK_THEME = """
QMainWindow {
    background-color: #0A0E27;
    border: 1px solid #1a1f3a;
    border-radius: 12px;
}
QWidget {
    background-color: #0A0E27;
    color: #E0E6FF;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}
QLabel { 
    color: #E0E6FF; 
    background: transparent;
}

/* Modern Button Style */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2a2f4d, stop:1 #1f2340);
    border: 1px solid #3a3f5d;
    border-radius: 6px;
    padding: 8px 16px;
    color: #E0E6FF;
    font-weight: 500;
    transition: all 200ms;
}
QPushButton:hover { 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a3f5d, stop:1 #2a2f4d);
    border: 1px solid #5a5f7d;
}
QPushButton:pressed { 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00D9FF, stop:1 #00B8D4);
    color: #000;
    border: 1px solid #00D9FF;
}

/* Slider Styles - Modern */
QSlider::groove:horizontal {
    background: #1a1f3a;
    height: 5px;
    border-radius: 2px;
    margin: 0px;
}
QSlider::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00D9FF, stop:1 #00B8D4);
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    border: 2px solid #0a0e27;
    box-shadow: 0 0 10px rgba(0, 217, 255, 0.5);
}
QSlider::handle:horizontal:hover {
    box-shadow: 0 0 15px rgba(0, 217, 255, 0.8);
}
QSlider::sub-page:horizontal { 
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D9FF, stop:1 #00B8D4);
    border-radius: 2px;
}
QSlider::add-page:horizontal { background: #1a1f3a; border-radius: 2px; }

/* Vertical Slider Styles - FIXED */
QSlider::groove:vertical {
    background: #1a1f3a;
    width: 5px;
    border-radius: 2px;
}
QSlider::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00D9FF, stop:1 #00B8D4);
    width: 16px;
    height: 16px;
    margin: 0 -6px;
    border-radius: 8px;
    border: 2px solid #0a0e27;
    box-shadow: 0 0 10px rgba(0, 217, 255, 0.5);
}
QSlider::handle:vertical:hover {
    box-shadow: 0 0 15px rgba(0, 217, 255, 0.8);
}
/* Vertical slider: add-page is BELOW the handle (filled) */
QSlider::add-page:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00D9FF, stop:1 #00B8D4);
    border-radius: 2px;
}
/* sub-page is ABOVE the handle (empty) */
QSlider::sub-page:vertical {
    background: #1a1f3a;
    border-radius: 2px;
}

/* Title Bar */
QWidget#title_bar {
    background-color: #0F1429;
    border-bottom: 1px solid #1a1f3a;
}

QLabel#titlelabel {
    color: #E0E6FF;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-weight: 600;
    font-size: 14px;
    padding: 0;
    margin: 0;
    min-height: 30px;
    max-height: 30px;
}

/* Control Panel - Modern Style */
QWidget#control_panel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 rgba(20, 25, 50, 200), stop:1 rgba(10, 14, 39, 240));
    border-top: 1px solid rgba(0, 217, 255, 0.3);
    border-radius: 12px 12px 0 0;
}

/* Title-bar and quick-action buttons */
QToolButton#quickbutton, QToolButton#settingsbutton,
QPushButton#minimizebutton, QPushButton#maximizebutton, QPushButton#closebutton {
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #A0A6C0;
    font-size: 13px;
    font-weight: 600;
    padding: 0;
    border-radius: 8px;
    min-height: 30px;
}
QToolButton#settingsbutton { font-size: 17px; padding: 0; min-width: 30px; max-width: 30px; }
QToolButton#quickbutton { min-width: 0; }
QPushButton#minimizebutton, QPushButton#maximizebutton, QPushButton#closebutton {
    min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; padding: 0; font-size: 16px; font-family: 'Segoe UI Symbol', 'Segoe UI';
}
QToolButton#quickbutton:hover, QToolButton#settingsbutton:hover,
QPushButton#minimizebutton:hover, QPushButton#maximizebutton:hover {
    background: rgba(0, 217, 255, 0.14);
    border-color: rgba(0, 217, 255, 0.28);
    color: #00D9FF;
}
QPushButton#closebutton:hover {
    background: rgba(255, 71, 87, 0.18);
    border-color: rgba(255, 71, 87, 0.3);
    color: #FF6675;
}

/* Scrollbar */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(0, 217, 255, 0.4);
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(0, 217, 255, 0.6);
}

/* Menu */
QMenu {
    background: #1a1f3a;
    color: #E0E6FF;
    border: 1px solid #3a3f5d;
    border-radius: 8px;
    padding: 8px 0;
}
QMenu::item:selected {
    background: rgba(0, 217, 255, 0.2);
    color: #00D9FF;
}

/* ComboBox */
QComboBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2a2f4d, stop:1 #1f2340);
    border: 1px solid #3a3f5d;
    border-radius: 6px;
    padding: 6px 12px;
    color: #E0E6FF;
}
QComboBox::drop-down {
    border: none;
    width: 26px;
}
QComboBox::down-arrow {
    width: 0px; height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #A0A6C0;
}
"""

LIGHT_THEME = """
QMainWindow {
    background-color: #F5F7FA;
    border: 1px solid #E0E6F0;
    border-radius: 12px;
}
QWidget {
    background-color: #F5F7FA;
    color: #1A1F3A;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}
QLabel { 
    color: #1A1F3A;
    background: transparent;
}

/* Button Style */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F0F2F5);
    border: 1px solid #D0D6E0;
    border-radius: 6px;
    padding: 8px 16px;
    color: #1A1F3A;
    font-weight: 500;
}
QPushButton:hover { 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0F2F5, stop:1 #E8EAEF);
    border: 1px solid #B8BFC8;
}
QPushButton:pressed { 
    background: #0078D4;
    color: white;
    border: 1px solid #0078D4;
}

/* Horizontal Slider */
QSlider::groove:horizontal {
    background: #D0D6E0;
    height: 5px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0078D4, stop:1 #005BA4);
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    border: 2px solid #F5F7FA;
}
QSlider::sub-page:horizontal { 
    background: #0078D4;
    border-radius: 2px;
}
QSlider::add-page:horizontal { background: #D0D6E0; border-radius: 2px; }

/* Vertical Slider - FIXED */
QSlider::groove:vertical {
    background: #D0D6E0;
    width: 5px;
    border-radius: 2px;
}
QSlider::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0078D4, stop:1 #005BA4);
    width: 16px;
    height: 16px;
    margin: 0 -6px;
    border-radius: 8px;
    border: 2px solid #F5F7FA;
}
/* Vertical slider: add-page is BELOW the handle (filled) */
QSlider::add-page:vertical {
    background: #0078D4;
    border-radius: 2px;
}
/* sub-page is ABOVE the handle (empty) */
QSlider::sub-page:vertical {
    background: #D0D6E0;
    border-radius: 2px;
}

QWidget#title_bar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E0E6F0;
}
QLabel#titlelabel {
    color: #1A1F3A;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-weight: 600;
    font-size: 14px;
    padding: 0;
    margin: 0;
    min-height: 30px;
    max-height: 30px;
}

QWidget#control_panel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,245), stop:1 rgba(241,244,248,252));
    border-top: 1px solid rgba(0, 120, 212, 0.18);
}

QToolButton#quickbutton, QToolButton#settingsbutton,
QPushButton#minimizebutton, QPushButton#maximizebutton, QPushButton#closebutton {
    background: rgba(255,255,255,0.78);
    border: 1px solid #D7DDE6;
    color: #4A5362;
    border-radius: 8px;
    font-weight: 600;
    min-height: 30px;
    padding: 0;
}
QToolButton#settingsbutton { font-size: 17px; padding: 0; min-width: 30px; max-width: 30px; }
QToolButton#quickbutton { min-width: 0; }
QPushButton#minimizebutton, QPushButton#maximizebutton, QPushButton#closebutton {
    min-width:30px; max-width:30px; min-height:30px; max-height:30px;
    padding:0; font-size:16px; font-family:'Segoe UI Symbol','Segoe UI';
}
QToolButton#quickbutton:hover, QToolButton#settingsbutton:hover, QPushButton#minimizebutton:hover, QPushButton#maximizebutton:hover {
    background: #EAF3FF; border-color: #B8D4F2; color: #006CC9;
}
QPushButton#closebutton:hover { background: #FFF0F1; border-color:#F1B9BE; color:#D63B48; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
    width: 0px; height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #5B6575;
}
"""

# Border detection size
BORDER_SIZE = 10  # widened for easier grabbing

# Force ffmpeg-python to use a bundled ffmpeg if present next to the app
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    # sys._MEIPASS is PyInstaller's self-deleting extraction folder - the
    # audio cache needs a location that survives between runs, so use the
    # real executable's directory instead.
    app_dir = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)
    app_dir = base_path

# Extracted audio tracks are cached here instead of the OS temp dir, so they
# can be reliably cleaned on our own schedule (see AudioManager.prune_cache_dir)
# regardless of how the OS temp dir behaves or whether a previous run crashed.
AUDIO_CACHE_DIR = os.path.join(app_dir, "audio_cache")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

# Add to PATH so subprocess ffmpeg/ffprobe calls find them
os.environ["PATH"] = base_path + os.pathsep + os.environ.get("PATH", "")

# ------------------------------ Video Player ------------------------------ #
class VideoPlayer(QWidget):
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    state_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.normal_geometry = None
        self.media_player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.setAcceptDrops(True)
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
        # QVideoWidget's native window intercepts mouse events before Qt's DnD -
        # make it transparent so drag&drop falls through to VideoPlayer (self).
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_widget)
        self.setLayout(layout)

        self.media_player.setVideoOutput(self.video_widget)

        self.media_player.positionChanged.connect(lambda pos: self.position_changed.emit(int(pos)))
        self.media_player.durationChanged.connect(lambda dur: self.duration_changed.emit(int(dur)))
        self.media_player.playbackStateChanged.connect(self.playback_state_changed)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                window = self.window()
                if hasattr(window, "load_video_from_path"):
                    window.load_video_from_path(path)
                event.acceptProposedAction()
                return
        event.ignore()

    def playback_state_changed(self, state):
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.state_changed.emit(is_playing)

    def set_media(self, file_path: str):
        self.media_player.setSource(QUrl.fromLocalFile(file_path))

    def set_video_muted(self):
        self.media_player.setAudioOutput(None)

    def play(self):
        self.media_player.play()

    def pause(self):
        self.media_player.pause()

    def stop(self):
        self.media_player.stop()

    def pos(self):
        return self.media_player.position()

    def dur(self):
        return self.media_player.duration()

    def set_pos(self, pos):
        self.media_player.setPosition(pos)

# ------------------------------ Audio Manager (supports N tracks) ------------------------------ #
class AudioManager(QObject):
    audio_tracks_detected = pyqtSignal(int)
    track_extract_progress = pyqtSignal(int, int)  # (done, total)

    def __init__(self, parent=None):
        super().__init__(parent)

        # dynamic lists for arbitrary number of tracks
        self.audio_players = []   # list of QMediaPlayer
        self.audio_outputs = []   # list of QAudioOutput
        self.temp_files = []
        self.ffmpeg_subprocesses = []
        self._cancel_extraction = False

    def stop_and_release_players(self):
        """Stop and destroy the current QMediaPlayer/QAudioOutput objects
        (releasing their file handles) WITHOUT deleting the underlying WAV
        files. Used when switching to a new video: the previous video's
        tracks stay in the cache dir (subject to prune_cache_dir's size
        limit) instead of being wiped just because playback moved on."""
        self._delete_audio_players()
        self.audio_players = []
        self.audio_outputs = []
        self.temp_files = []

    def cleanup_temp_files(self):
        # Used on cancel/error paths, where the in-progress files really are
        # abandoned rather than meant to stay cached for later reuse.
        self._delete_audio_players()
        self.audio_players = []
        self.audio_outputs = []
        # remove temporary files - retry briefly in case Qt hasn't finished
        # processing the deleteLater() yet
        for f in self.temp_files:
            for attempt in range(3):
                try:
                    os.unlink(f)
                    break
                except FileNotFoundError:
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(0.05)
        self.temp_files = []

    def clear_cache_dir(self):
        """Delete every file in AUDIO_CACHE_DIR. Used on app close and
        optionally on startup - a full wipe rather than tracking individual
        files, so nothing can be missed by a crash or a file that was still
        locked during a prior cleanup attempt."""
        try:
            for name in os.listdir(AUDIO_CACHE_DIR):
                path = os.path.join(AUDIO_CACHE_DIR, name)
                if not os.path.isfile(path):
                    continue
                # Retry briefly - a player may have only just stop()'d and
                # not released its file handle yet (mainly on Windows).
                for attempt in range(3):
                    try:
                        os.unlink(path)
                        break
                    except FileNotFoundError:
                        break
                    except Exception:
                        if attempt < 2:
                            time.sleep(0.05)
        except Exception:
            pass

    def prune_cache_dir(self, limit_mb: int):
        """Delete the oldest files in AUDIO_CACHE_DIR until total size is
        back under limit_mb. Called after extraction so the cache never
        grows unbounded across many video loads within one session."""
        limit_bytes = max(0, int(limit_mb)) * 1024 * 1024
        try:
            entries = []
            total = 0
            for name in os.listdir(AUDIO_CACHE_DIR):
                path = os.path.join(AUDIO_CACHE_DIR, name)
                try:
                    if os.path.isfile(path):
                        stat = os.stat(path)
                        entries.append((stat.st_mtime, stat.st_size, path))
                        total += stat.st_size
                except Exception:
                    pass

            if total <= limit_bytes:
                return

            # Oldest first; skip files currently in use (self.temp_files)
            in_use = set(self.temp_files)
            entries.sort(key=lambda e: e[0])
            for mtime, size, path in entries:
                if total <= limit_bytes:
                    break
                if path in in_use:
                    continue
                try:
                    os.unlink(path)
                    total -= size
                except Exception:
                    pass
        except Exception:
            pass

    def probe_media(self, file_path: str):
        """Single ffprobe call: audio track count + video resolution + duration together."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=index,codec_type,width,height:format=duration",
                "-of", "json",
                file_path,
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            data = json.loads(result.stdout) if result.stdout else {}
            streams = data.get("streams", [])
            audio_count = sum(1 for s in streams if s.get("codec_type") == "audio")
            video_stream = next(
                (s for s in streams if s.get("codec_type") == "video" and "width" in s and "height" in s),
                None
            )
            if video_stream:
                width, height = int(video_stream["width"]), int(video_stream["height"])
            else:
                width, height = 1280, 720
            try:
                duration_seconds = float(data.get("format", {}).get("duration", 0))
            except (TypeError, ValueError):
                duration_seconds = 0.0
            return audio_count, width, height, duration_seconds
        except Exception:
            return 0, 1280, 720, 0.0

    def detect_audio_tracks(self, file_path: str) -> int:
        # Wraps probe_media()
        audio_count, _, _, _ = self.probe_media(file_path)
        self.audio_tracks_detected.emit(audio_count)
        return audio_count

    def extract_audio_tracks(self, file_path: str, num_audio_tracks: int = None, max_tracks: int = None, cache_limit_mb: int = 2000, duration_seconds: float = 0.0):
        # Extract all audio tracks with live progress tracking based on output file size.
        # Stop/release the previous video's players without deleting their
        # cached files - prune_cache_dir() below handles eviction by size.
        self.stop_and_release_players()
        if num_audio_tracks is None:
            num_audio_tracks = self.detect_audio_tracks(file_path)
        if num_audio_tracks == 0:
            return []

        total_to_extract = num_audio_tracks if max_tracks is None else min(num_audio_tracks, max_tracks)
        self._cancel_extraction = False
        
        # Launch ffmpeg for every track in parallel
        jobs = []  # (track_index, temp_path, process)
        all_created_paths = []  # every temp file created this call, success or not - for cleanup

        for i in range(total_to_extract):
            temp_path = os.path.join(AUDIO_CACHE_DIR, f"{uuid.uuid4().hex}.wav")
            all_created_paths.append(temp_path)
            try:
                # Track file size instead of parsing progress output
                cmd = (
                    ffmpeg
                    .input(file_path)
                    .output(temp_path, map=f"0:a:{i}", af="volume=5.0", ac=2, ar="44100")
                    .overwrite_output()
                    .compile()
                )
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                self.ffmpeg_subprocesses.append(proc)
                jobs.append((i, temp_path, proc))
            except Exception:
                break

        # Monitor output file sizes in a background thread to estimate progress.
        def monitor_all_tracks():
            num_jobs = len(jobs)
            # Exact expected size per track: PCM WAV at 44.1kHz/16-bit/stereo
            # is 176400 bytes/sec, regardless of video length. Using the
            # real duration (known from probe_media) instead of a fixed
            # "typical track" guess fixes wildly wrong progress on videos
            # much longer or shorter than a few minutes.
            bytes_per_sec = 44100 * 2 * 2
            if duration_seconds > 0:
                expected_total = int(bytes_per_sec * duration_seconds * num_jobs)
            else:
                expected_total = 20 * 1024 * 1024 * num_jobs  # fallback if duration is unknown

            while any(proc.poll() is None for _, _, proc in jobs) and not self._cancel_extraction:
                total_size = 0

                for track_idx, temp_path, proc in jobs:
                    try:
                        if os.path.exists(temp_path):
                            total_size += os.path.getsize(temp_path)
                    except Exception:
                        pass

                if expected_total > 0:
                    percent = int((total_size / expected_total) * 100)
                else:
                    percent = 0
                percent = min(99, max(0, percent))

                if percent > 0:
                    self.track_extract_progress.emit(0, percent)

                time.sleep(0.5)  # ~2 updates/sec

            self.track_extract_progress.emit(0, 100)
        
        # Monitor in a background thread
        monitor_thread = threading.Thread(target=monitor_all_tracks, daemon=True)
        monitor_thread.start()
        
        # Wait for all processes to finish
        failed_paths = []
        for track_idx, temp_path, proc in jobs:
            try:
                proc.wait()
                if proc.returncode == 0:
                    self.temp_files.append(temp_path)
                else:
                    failed_paths.append(temp_path)
            except Exception:
                failed_paths.append(temp_path)

        # Anything created but never queued (Popen raised before appending to
        # jobs) or that failed/was cancelled isn't in self.temp_files and
        # won't be cleaned up by cleanup_temp_files() later - remove it now
        # instead of leaking a WAV file on every failed/cancelled load.
        succeeded = set(self.temp_files)
        leftover = [p for p in all_created_paths if p not in succeeded]
        for p in leftover:
            try:
                os.unlink(p)
            except Exception:
                pass

        # Keep the cache dir under the configured size limit, oldest first.
        self.prune_cache_dir(cache_limit_mb)

        return self.temp_files

    def setup_audio_players(self):
        """Create Qt audio objects in the GUI thread after extraction."""
        self._delete_audio_players()
        self.audio_players = []
        self.audio_outputs = []
        for path in self.temp_files:
            player = QMediaPlayer(self)
            audio_out = QAudioOutput(self)
            player.setAudioOutput(audio_out)
            audio_out.setVolume(0.25)
            player.setSource(QUrl.fromLocalFile(path))
            self.audio_players.append(player)
            self.audio_outputs.append(audio_out)

    def _delete_audio_players(self):
        """Actually destroy the current QMediaPlayer/QAudioOutput objects
        instead of just dropping the Python list. They're created with
        parent=self (AudioManager), so the C++ parent keeps them alive for
        the whole app session unless explicitly deleted - meaning their
        open file handles on the extracted WAVs never released, which is
        why cache files couldn't be deleted mid-session no matter what
        cleanup/prune ran."""
        for p in self.audio_players:
            try:
                p.stop()
                p.setSource(QUrl())  # release the file handle before deleting
                p.setParent(None)
                p.deleteLater()
            except Exception:
                pass
        for out in self.audio_outputs:
            try:
                out.setParent(None)
                out.deleteLater()
            except Exception:
                pass

    def play(self):
        for p in self.audio_players:
            try:
                p.play()
            except Exception:
                pass

    def pause(self):
        for p in self.audio_players:
            try:
                p.pause()
            except Exception:
                pass

    def stop(self):
        for p in self.audio_players:
            try:
                p.stop()
            except Exception:
                pass

    def set_pos(self, pos):
        # pos in milliseconds
        for p in self.audio_players:
            try:
                p.setPosition(pos)
            except Exception:
                pass

    # Tracks are separate QMediaPlayer instances with independent decode
    # clocks, so they can drift apart from the video over time, and one can
    # silently stall (buffering underrun / device glitch) without the others
    # noticing. Pause alone doesn't fix a stalled player - pause() only
    # affects players that are actually still playing, and a stalled one is
    # already stopped, so there's nothing for it to catch.
    DRIFT_THRESHOLD_MS = 300

    def resync(self, video_pos: int, video_should_play: bool):
        """Called periodically during playback. Restarts any track that has
        silently stopped while it should be playing, and repositions any
        track that has drifted more than DRIFT_THRESHOLD_MS from the video."""
        if not video_should_play:
            return
        for p in self.audio_players:
            try:
                state = p.playbackState()
                drifted = abs(p.position() - video_pos) > self.DRIFT_THRESHOLD_MS
                stalled = state != QMediaPlayer.PlaybackState.PlayingState
                if stalled or drifted:
                    p.setPosition(video_pos)
                if stalled:
                    p.play()
            except Exception:
                pass

    def set_track_vol(self, index: int, gain: float):
        # gain in 0..1
        if 0 <= index < len(self.audio_outputs):
            try:
                self.audio_outputs[index].setVolume(gain)
            except Exception:
                pass

    def cleanup_on_close(self):
        for p in self.ffmpeg_subprocesses:
            try:
                p.terminate()
            except Exception:
                pass

        self._delete_audio_players()
        self.audio_players = []
        self.audio_outputs = []
        self.ffmpeg_subprocesses = []

# ------------------------------ Control Panel (dynamic track controls) ------------------------------ #
class ClickableSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dragging = False

    def _value_from_pos(self, pos):
        # Clamp to widget bounds - mouse can drag outside while held down
        if self.orientation() == Qt.Orientation.Horizontal:
            x = max(0, min(self.width(), int(pos.x())))
            return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), x, self.width())
        else:
            y = max(0, min(self.height(), int(pos.y())))
            return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), self.height() - y, self.height())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            value = self._value_from_pos(event.position())
            self.setValue(value)

            # Grab mouse so drag keeps working even outside widget bounds
            self._dragging = True
            self.grabMouse()

            self.sliderPressed.emit()
            self.sliderMoved.emit(value)

            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            value = self._value_from_pos(event.position())
            self.setValue(value)
            self.sliderMoved.emit(value)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.releaseMouse()
            self.sliderReleased.emit()
            event.accept()
            return

        super().mouseReleaseEvent(event)


# Background audio extraction thread
class AudioExtractorThread(QThread):
    extraction_finished = pyqtSignal(list)   # list of temp file paths
    extraction_progress = pyqtSignal(str)
    extraction_error = pyqtSignal(str)
    audio_tracks_detected = pyqtSignal(int)
    video_resolution_detected = pyqtSignal(int, int)  # from the same ffprobe call

    def __init__(self, file_path, audio_manager, cache_limit_mb=2000, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.audio_manager = audio_manager
        self.cache_limit_mb = cache_limit_mb
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        for proc in self.audio_manager.ffmpeg_subprocesses:
            try:
                proc.terminate()
            except Exception:
                pass

    def run(self):
        try:
            # One ffprobe call: audio track count + video resolution + duration
            num_audio_tracks, width, height, duration_seconds = self.audio_manager.probe_media(self.file_path)
            if self._is_cancelled:
                return
            self.audio_tracks_detected.emit(num_audio_tracks)
            self.video_resolution_detected.emit(width, height)

            if num_audio_tracks == 0:
                self.extraction_finished.emit([])
                return

            self.extraction_progress.emit("Extracting audio tracks...")
            temp_files = self.audio_manager.extract_audio_tracks(
                self.file_path, num_audio_tracks, cache_limit_mb=self.cache_limit_mb,
                duration_seconds=duration_seconds
            )
            
            if self._is_cancelled:
                self.audio_manager.cleanup_temp_files()
                return

            if not temp_files:
                self.extraction_error.emit("Failed to extract audio tracks.")
                return

            self.extraction_finished.emit(temp_files)

        except Exception as e:
            if not self._is_cancelled:
                self.extraction_error.emit(f"Extraction failed: {str(e)}")

# Background export thread with progress and cancel support
class ExportThread(QThread):
    export_finished = pyqtSignal(bool, str)  # (success, output_path_or_error_message)
    progress_changed = pyqtSignal(int)  # percent 0-100
    export_cancelled = pyqtSignal()

    def __init__(self, cmd, output_path, duration_ms, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self.output_path = output_path
        self.duration_ms = max(1, duration_ms)  # guard against div-by-zero if duration wasn't known yet
        self._process = None
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def run(self):
        try:
            self._process = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge stderr into stdout
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            # ffmpeg's "-progress pipe:1" writes key=value lines, incl. out_time_ms
            last_percent = -1
            if self._process.stdout is not None:
                for line in self._process.stdout:
                    if self._is_cancelled:
                        break
                    line = line.strip()
                    if line.startswith("out_time_ms="):
                        try:
                            out_time_ms = int(line.split("=", 1)[1]) / 1000.0  # ffmpeg reports microseconds
                            percent = int(max(0, min(100, out_time_ms / self.duration_ms * 100)))
                            if percent != last_percent:
                                last_percent = percent
                                self.progress_changed.emit(percent)
                        except Exception:
                            pass
                    elif line == "progress=end":
                        self.progress_changed.emit(100)

            returncode = self._process.wait()

            if self._is_cancelled:
                try:
                    if os.path.exists(self.output_path):
                        os.remove(self.output_path)
                except Exception:
                    pass
                self.export_cancelled.emit()
                return

            if returncode == 0:
                self.export_finished.emit(True, self.output_path)
            else:
                self.export_finished.emit(False, "Export failed")
        except Exception as e:
            self.export_finished.emit(False, str(e))

class ControlPanel(QWidget):
    open_request = pyqtSignal()
    play_request = pyqtSignal()
    stop_request = pyqtSignal()
    timeline_pressed = pyqtSignal()
    timeline_released = pyqtSignal()
    timeline_moved = pyqtSignal(int)
    # unified signal: (track_index, value)
    track_vol_chg = pyqtSignal(int, int)
    track_mute_chg = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("control_panel")
        
        # Control buttons with modern styling
        self.open_button = QPushButton("Open")
        self.play_button = QPushButton("▶")
        self._set_play_button_visual(False)
        self.stop_button = QPushButton("■")
        
        for btn in [self.open_button, self.play_button, self.stop_button]:
            btn.setMinimumHeight(38)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.open_button.setToolTip("Open video")
        self.play_button.setToolTip("Play / Pause")
        self.stop_button.setToolTip("Stop")
        self.play_button.setMinimumWidth(56)
        self.stop_button.setMinimumWidth(56)

        # Timeline slider with label
        self.timeline_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timeline_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.timeline_label = QLabel("00:00 / 00:00")
        self.timeline_label.setMinimumWidth(100)
        self.timeline_label.setStyleSheet("font-size: 12px; font-weight: 500; opacity: 0.8;")

        # Info label with better styling
        self.info_label = QLabel("No File Loaded")
        self.info_label.setStyleSheet("font-size: 13px; margin: 6px 0; min-height: 20px;")

        # The dynamic track controls area (scrollable if many tracks)
        self.track_controls_area = QScrollArea()
        self.track_controls_area.setWidgetResizable(True)
        self.track_controls_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: 1px solid rgba(0, 217, 255, 0.2);
                border-radius: 6px;
            }
        """)
        self.track_controls_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.track_controls_area.setMaximumHeight(200)
        self.track_container = QWidget()
        self.track_controls_layout = QVBoxLayout(self.track_container)
        self.track_controls_layout.setContentsMargins(8, 8, 8, 8)
        self.track_controls_layout.setSpacing(8)
        self.track_container.setLayout(self.track_controls_layout)
        self.track_controls_area.setWidget(self.track_container)

        # ----- Layouts ----- #
        # Timeline area
        timeline_layout = QHBoxLayout()
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(8)
        timeline_layout.addWidget(self.timeline_label)
        timeline_layout.addWidget(self.timeline_slider, 1)

        # Volume/tracks area
        volume_label = QLabel("Audio Tracks:")
        volume_label.setStyleSheet("font-size: 12px; font-weight: 500; opacity: 0.7; margin-top: 8px;")
        volume_container_layout = QVBoxLayout()
        volume_container_layout.setContentsMargins(0, 0, 0, 0)
        volume_container_layout.setSpacing(6)
        volume_container_layout.addWidget(volume_label)
        volume_container_layout.addWidget(self.track_controls_area)

        # Controls buttons area
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 8, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)

        # ----- Main Container ----- #
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        main_layout.addLayout(timeline_layout)
        main_layout.addWidget(self.info_label)
        main_layout.addLayout(volume_container_layout, stretch=1)
        main_layout.addLayout(controls_layout, stretch=0)

        # Connections
        self.open_button.clicked.connect(lambda: self.open_request.emit())
        self.play_button.clicked.connect(lambda: self.play_request.emit())
        self.stop_button.clicked.connect(lambda: self.stop_request.emit())

        self.timeline_slider.sliderPressed.connect(lambda: self.timeline_pressed.emit())
        self.timeline_slider.sliderReleased.connect(lambda: self.timeline_released.emit())
        self.timeline_slider.sliderMoved.connect(lambda pos: self.timeline_moved.emit(pos))

        # internal storage of controls for label updates
        self._track_widgets = []  # list of (label_widget, slider_widget, vol_label_widget)
        self._track_mutes = []    # list of mute QCheckBox, parallel to _track_widgets

    def clear_track_controls(self):
        # Remove existing controls
        for i in reversed(range(self.track_controls_layout.count())):
            item = self.track_controls_layout.itemAt(i)
            if item:
                w = item.widget()
                if w:
                    w.setParent(None)
        self._track_widgets = []
        self._track_mutes = []

    def populate_track_controls(self, num_tracks: int, orientation="horizontal", max_volume=400):
        # Create N sliders/labels for audio tracks with specified orientation
        max_volume = max(1, int(max_volume))  # never allow a 0 division below
        self.clear_track_controls()
        
        # Adjust scroll area behavior and sizing based on orientation
        if orientation == "vertical":
            # Vertical sliders don't need scrolling - they fill the space
            self.track_controls_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.track_controls_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            # Let the content size itself naturally - no constraints
            # NOTE: each column stacks a label + slider (up to 200px) + volume
            # label + Mute checkbox, plus layout spacing/margins. The old cap
            # of 240px was shorter than that stack, so the Mute checkbox at
            # the bottom got clipped (the scrollbar is intentionally off above).
            self.track_controls_area.setMinimumHeight(0)
            self.track_controls_area.setMaximumHeight(16777215)
            self.track_controls_area.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum  # Take only what content needs
            )
        else:
            # Horizontal sliders might need scrolling if many tracks
            self.track_controls_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.track_controls_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            # No scrolling until more than four tracks.
            row_height = 42
            visible_rows = min(num_tracks, 4)

            self.track_controls_area.setMinimumHeight(row_height * visible_rows + 10)
            self.track_controls_area.setMaximumHeight(row_height * visible_rows + 10)
            self.track_controls_area.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred
            )
        
        if orientation == "vertical":
            # For vertical sliders, arrange them horizontally (left to right)
            sliders_container = QWidget()
            sliders_layout = QHBoxLayout(sliders_container)
            sliders_layout.setContentsMargins(5, 5, 5, 5)
            sliders_layout.setSpacing(15)
            sliders_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            
            for i in range(num_tracks):
                slider_widget = QWidget()
                slider_layout = QVBoxLayout(slider_widget)
                slider_layout.setContentsMargins(0, 0, 0, 0)
                slider_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                slider_layout.setSpacing(5)
                
                label = QLabel(f"Track {i+1}")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                slider = ClickableSlider(Qt.Orientation.Vertical)
                slider.setRange(0, 100)
                # Default slider value maps to 100% volume for any max_volume
                default_slider = int(10000 / max_volume)
                slider.setValue(default_slider)
                slider.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
                slider.setMinimumHeight(100)
                slider.setMaximumHeight(200)
                
                default_percent = int(default_slider * max_volume / 100)
                vol_label = QLabel(f"{default_percent}%")
                vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                mute_box = QCheckBox("Mute")

                slider_layout.addWidget(label)
                slider_layout.addWidget(slider, 1)
                slider_layout.addWidget(vol_label)
                slider_layout.addWidget(mute_box)

                slider.valueChanged.connect(partial(self._on_track_slider_changed, i))
                mute_box.toggled.connect(partial(self._on_track_mute_toggled, i))
                sliders_layout.addWidget(slider_widget)
                self._track_widgets.append((label, slider, vol_label))
                self._track_mutes.append(mute_box)
            
            self.track_controls_layout.addWidget(sliders_container)
            self.track_controls_area.setFixedHeight(
                sliders_container.sizeHint().height() + 10
            )
        else:
            # Horizontal sliders (original)
            for i in range(num_tracks):
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                label = QLabel(f"Track {i+1} Volume:")
                slider = ClickableSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, 100)
                # Default slider value maps to 100% volume for any max_volume
                default_slider = int(10000 / max_volume)
                slider.setValue(default_slider)
                default_percent = int(default_slider * max_volume / 100)
                vol_label = QLabel(f"{default_percent}%")
                mute_box = QCheckBox("Mute")
                mute_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                slider.valueChanged.connect(partial(self._on_track_slider_changed, i))
                mute_box.toggled.connect(partial(self._on_track_mute_toggled, i))
                row_layout.addWidget(label)
                row_layout.addWidget(slider)
                row_layout.addWidget(vol_label)
                row_layout.addWidget(mute_box)
                self.track_controls_layout.addWidget(row)
                self._track_widgets.append((label, slider, vol_label))
                self._track_mutes.append(mute_box)
        
        if num_tracks == 0:
            hint = QLabel("No audio tracks.")
            self.track_controls_layout.addWidget(hint)


    def _on_track_slider_changed(self, index: int, value: int):
        # Slider value 0-100 mapped to 0-max_volume% (stored in parent MainWindow)
        # Get max_volume from parent if available
        parent_window = self.parent()
        if parent_window and hasattr(parent_window, 'max_volume'):
            max_vol = parent_window.max_volume
        else:
            max_vol = 400  # fallback
        display_percentage = int(value * max_vol / 100)
        # update label
        try:
            _, _, vol_label = self._track_widgets[index]
            vol_label.setText(f"{display_percentage}%")
        except Exception:
            pass
        # emit unified signal
        self.track_vol_chg.emit(index, value)

    def _on_track_mute_toggled(self, index: int, muted: bool):
        # Disable slider while muted, avoids conflicting volume state
        try:
            _, slider, _ = self._track_widgets[index]
            slider.setEnabled(not muted)
        except Exception:
            pass
        self.track_mute_chg.emit(index, muted)

    def _set_play_button_visual(self, playing: bool):
        """Keep Play and Pause optically balanced despite different glyph widths."""
        self.play_button.setText("▮▮" if playing else "▶")
        font = self.play_button.font()
        font.setPointSize(15)
        self.play_button.setFont(font)

    # convenience helpers used by MainWindow
    def set_timeline_range(self, maximum):
        self.timeline_slider.setRange(0, maximum)

    def set_timeline_value_blocked(self, value):
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(value)
        self.timeline_slider.blockSignals(False)

    def set_timeline_label(self, text):
        self.timeline_label.setText(text)

    def set_info_text(self, text):
        self.info_label.setText(text)

    def set_track_vol_label(self, index: int, text: str):
        # set the small percent label for a given track index (if exists)
        try:
            _, _, vol_label = self._track_widgets[index]
            vol_label.setText(text)
        except Exception:
            pass

# ------------------------------ Settings Dialog ----------------------------- #
class SettingsDialog(QDialog):
    """Organized application settings window.

    The dialog owns the settings UI while MainWindow owns the actual player
    behavior. Changes are applied immediately and persisted through MainWindow.
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Crusty Media Player — Settings")
        self.setMinimumSize(760, 520)
        self.resize(820, 560)
        self.setModal(True)

        self.category_list = QListWidget()
        self.setObjectName("settings_dialog")
        self.category_list.setFixedWidth(190)
        self.category_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.category_list.addItems([
            "Appearance",
            "Playback",
            "Controls",
            "Files & Help",
        ])

        self.pages = QStackedWidget()
        self._build_appearance_page()
        self._build_playback_page()
        self._build_controls_page()
        self._build_files_page()

        self.category_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.category_list.setCurrentRow(0)
        self._disable_text_focus_on_controls()

        close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_button.rejected.connect(self.reject)
        close_button.accepted.connect(self.accept)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(12, 12, 12, 8)
        content_layout.setSpacing(14)
        content_layout.addWidget(self.category_list)
        content_layout.addWidget(self.pages, 1)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addLayout(content_layout, 1)
        root_layout.addWidget(close_button)

    def _disable_text_focus_on_controls(self):
        """Buttons/selection widgets should not leave Qt's text focus rectangle behind."""
        for widget in self.findChildren((QPushButton, QToolButton, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox)):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _page(self, title, description=""):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title_label)

        if description:
            description_label = QLabel(description)
            description_label.setWordWrap(True)
            description_label.setStyleSheet("opacity: 0.8;")
            layout.addWidget(description_label)

        return page, layout

    def _build_appearance_page(self):
        page, layout = self._page(
            "Appearance",
            "Choose the interface theme. The change is applied immediately."
        )

        group = QGroupBox("Theme")
        form = QFormLayout(group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        form.addRow("Theme:", self.theme_combo)

        self.fullscreen_start_check = QCheckBox("Start in fullscreen")
        form.addRow("", self.fullscreen_start_check)

        self.theme_combo.currentIndexChanged.connect(
            lambda: self.main_window.apply_theme(self.theme_combo.currentData())
        )
        self.fullscreen_start_check.toggled.connect(
            self.main_window.set_fullscreen_on_start
        )

        layout.addWidget(group)
        layout.addStretch()
        self.pages.addWidget(page)

    def _build_playback_page(self):
        page, layout = self._page(
            "Playback",
            "Options that affect audio track controls and startup behavior."
        )

        group = QGroupBox("Playback behavior")
        form = QFormLayout(group)

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("Horizontal", "horizontal")
        self.orientation_combo.addItem("Vertical", "vertical")
        form.addRow("Track sliders:", self.orientation_combo)

        self.remember_volumes_check = QCheckBox("Remember volume levels")
        form.addRow("", self.remember_volumes_check)

        self.orientation_combo.currentIndexChanged.connect(
            lambda: self.main_window.set_slider_orientation(
                self.orientation_combo.currentData()
            )
        )
        self.remember_volumes_check.toggled.connect(
            self.main_window.set_remember_volumes
        )

        layout.addWidget(group)
        layout.addStretch()
        self.pages.addWidget(page)

    def _build_controls_page(self):
        page, layout = self._page(
            "Controls",
            "Configure automatic hiding and the area used to reveal the bottom controls."
        )

        group = QGroupBox("Control panel")
        form = QFormLayout(group)

        self.auto_hide_check = QCheckBox("Automatically hide controls while playing")
        form.addRow("", self.auto_hide_check)

        self.hide_delay_spin = QDoubleSpinBox()
        self.hide_delay_spin.setRange(0.1, 60.0)
        self.hide_delay_spin.setSingleStep(0.1)
        self.hide_delay_spin.setDecimals(1)
        self.hide_delay_spin.setSuffix(" s")
        form.addRow("Hide delay:", self.hide_delay_spin)

        self.reveal_zone_spin = QSpinBox()
        self.reveal_zone_spin.setRange(0, 1000)
        self.reveal_zone_spin.setSingleStep(10)
        self.reveal_zone_spin.setSuffix(" px")
        form.addRow("Bottom reveal zone:", self.reveal_zone_spin)

        self.max_volume_spin = QSpinBox()
        self.max_volume_spin.setRange(1, 1000)
        self.max_volume_spin.setSingleStep(10)
        self.max_volume_spin.setSuffix(" %")
        form.addRow("Maximum volume:", self.max_volume_spin)

        self.auto_hide_check.toggled.connect(self.main_window.set_auto_hide)
        self.hide_delay_spin.valueChanged.connect(
            lambda seconds: self.main_window.set_hide_delay(int(seconds * 1000))
        )
        self.reveal_zone_spin.valueChanged.connect(
            self.main_window.set_mouse_reveal_zone
        )
        self.max_volume_spin.valueChanged.connect(
            self.main_window.set_max_volume
        )

        layout.addWidget(group)
        layout.addStretch()
        self.pages.addWidget(page)

    def _build_files_page(self):
        page, layout = self._page(
            "Files & Help",
            "Maintenance actions and help for the player."
        )

        cache_group = QGroupBox("Audio cache")
        cache_form = QFormLayout(cache_group)

        self.cache_limit_spin = QSpinBox()
        self.cache_limit_spin.setRange(100, 100000)
        self.cache_limit_spin.setSingleStep(100)
        self.cache_limit_spin.setSuffix(" MB")
        cache_form.addRow("Cache size limit:", self.cache_limit_spin)
        self.cache_limit_spin.valueChanged.connect(self.main_window.set_audio_cache_limit)

        self.cache_size_label = QLabel()
        self.cache_size_label.setStyleSheet("opacity: 0.7;")
        cache_form.addRow("Current size:", self.cache_size_label)

        clear_cache_row = QHBoxLayout()
        clear_cache_button = QPushButton("Clear Cache Now")
        clear_cache_button.clicked.connect(self._on_clear_cache_clicked)
        clear_cache_row.addWidget(clear_cache_button)
        clear_cache_row.addStretch()
        cache_form.addRow("", clear_cache_row)

        actions_group = QGroupBox("Help")
        actions_layout = QHBoxLayout(actions_group)
        shortcuts_button = QPushButton("Keyboard Shortcuts")
        shortcuts_button.clicked.connect(self.main_window.show_keyboard_shortcuts)
        actions_layout.addWidget(shortcuts_button)
        actions_layout.addStretch()

        layout.addWidget(cache_group)
        layout.addWidget(actions_group)
        layout.addStretch()
        self.pages.addWidget(page)

    def _on_clear_cache_clicked(self):
        self.main_window.clear_audio_cache_now()
        self._refresh_cache_size_label()

    def _refresh_cache_size_label(self):
        size_mb = self.main_window.get_audio_cache_size_mb()
        self.cache_size_label.setText(f"{size_mb:.1f} MB")

    def refresh_values(self):
        settings = self.main_window.settings
        self.theme_combo.blockSignals(True)
        self.orientation_combo.blockSignals(True)
        self.remember_volumes_check.blockSignals(True)
        self.fullscreen_start_check.blockSignals(True)
        self.auto_hide_check.blockSignals(True)
        self.hide_delay_spin.blockSignals(True)
        self.reveal_zone_spin.blockSignals(True)
        self.max_volume_spin.blockSignals(True)
        self.cache_limit_spin.blockSignals(True)

        theme_index = self.theme_combo.findData(settings.get("theme", "dark"))
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)

        orientation_index = self.orientation_combo.findData(
            settings.get("slider_orientation", "horizontal")
        )
        if orientation_index >= 0:
            self.orientation_combo.setCurrentIndex(orientation_index)

        self.remember_volumes_check.setChecked(
            settings.get("remember_volumes", False)
        )
        self.fullscreen_start_check.setChecked(
            settings.get("fullscreen_on_start", False)
        )
        self.auto_hide_check.setChecked(
            settings.get("auto_hide_controls", True)
        )
        self.hide_delay_spin.setValue(
            settings.get("hide_delay", 2000) / 1000.0
        )
        self.reveal_zone_spin.setValue(
            int(settings.get("mouse_reveal_zone", 60))
        )
        self.max_volume_spin.setValue(
            int(settings.get("max_volume", 400))
        )
        self.cache_limit_spin.setValue(
            int(settings.get("audio_cache_limit_mb", 2000))
        )

        self.theme_combo.blockSignals(False)
        self.orientation_combo.blockSignals(False)
        self.remember_volumes_check.blockSignals(False)
        self.fullscreen_start_check.blockSignals(False)
        self.auto_hide_check.blockSignals(False)
        self.hide_delay_spin.blockSignals(False)
        self.reveal_zone_spin.blockSignals(False)
        self.max_volume_spin.blockSignals(False)
        self.cache_limit_spin.blockSignals(False)

        self._refresh_cache_size_label()

    def showEvent(self, event):
        self.refresh_values()
        super().showEvent(event)


# ------------------------------- Main Window ------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()
        self.max_volume = self.settings.get("max_volume", 400)
        self.extraction_thread = None
        self.export_thread = None
        self.normal_geometry = None  # saved window geometry (pre-fullscreen)
        self.window_transition = None
        self._fullscreen_transitioning = False
        self._drag_restore_start_size = None
        self._drag_restore_target_size = None
        self._drag_restore_elapsed = None
        self._drag_restore_duration = 180

        # Debounce disk writes: settings setters call queue_save_settings()
        # instead of save_settings() directly, so rapid changes (e.g.
        # scrolling a spinbox) collapse into a single write instead of one
        # per tick.
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(400)
        self._settings_save_timer.timeout.connect(lambda: save_settings(self.settings))

        # ----- Window Setup ----- #
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(200, 100, 1600, 900)
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        self.setAcceptDrops(True)

        # Core components
        self.video = VideoPlayer(self)
        self.audio = AudioManager(self)
        self.controls = ControlPanel(self)

        # Custom title bar
        self.title_bar = QWidget()
        self.title_bar.setMinimumHeight(30)
        self.title_bar.setMaximumHeight(30)
        self.title_bar.setObjectName("title_bar")
        self.title_label = QLabel(f"Crusty Media Player v{APP_VERSION}")
        self.title_label.setObjectName("titlelabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.title_label.setFixedHeight(30)

        # Settings are opened in a dedicated window instead of a popup menu.
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("Settings")
        self.settings_button.setFixedSize(30, 30)
        self.settings_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.settings_button.setObjectName("settingsbutton")
        self.settings_button.clicked.connect(self.open_settings)

        # Quick access: recent files and export stay outside Settings.
        self.recent_button = QToolButton()
        self.recent_button.setText("Recent")
        self.recent_button.setToolTip("Open a recently used video")
        self.recent_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.recent_button.setArrowType(Qt.ArrowType.NoArrow)
        self.recent_button.setFixedSize(84, 30)
        self.recent_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_menu = QMenu(self)
        self.recent_button.setMenu(self.recent_menu)
        self.recent_button.setObjectName("quickbutton")

        self.export_button = QToolButton()
        self.export_button.setText("Export")
        self.export_button.setToolTip("Export video with mixed audio")
        self.export_button.setObjectName("quickbutton")
        self.export_button.setFixedSize(74, 30)
        self.export_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.export_button.clicked.connect(self.export_video)

        self.settings_dialog = None

        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.setObjectName("closebutton")
        self.close_button.setToolTip("Close")
        self.close_button.clicked.connect(self.close)

        self.minimize_button = QPushButton("−")
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.minimize_button.setObjectName("minimizebutton")
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.clicked.connect(self.showMinimized)

        self.maximize_button = QPushButton("□")
        self.maximize_button.setFixedSize(30, 30)
        self.maximize_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.maximize_button.setObjectName("maximizebutton")
        self.maximize_button.setToolTip("Fullscreen (F)")
        self.maximize_button.clicked.connect(self.toggle_maximize)

        # ----- Layouts ----- #
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.recent_button)
        title_layout.addWidget(self.export_button)
        title_layout.addWidget(self.settings_button)
        title_layout.addWidget(self.minimize_button)
        title_layout.addWidget(self.maximize_button)
        title_layout.addWidget(self.close_button)
        title_layout.setContentsMargins(6, 0, 6, 0)

        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)
        video_layout.addWidget(self.video)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(video_container, stretch=1)
        main_layout.addWidget(self.controls)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.dragPos = QPoint()
        self._title_dragging = False
        self._drag_restore_pending = False
        self.is_playing = False
        self.is_scrubbing = False
        self.controls_visible = True
        self.current_video_path = None  # Store the currently loaded video path
        self._resync_tick_counter = 0
        self._detected_resolution = None
        self._pending_seek = None

        # ----- Live frame preview while dragging the timeline slider ----- #
        self._pending_scrub_pos = None
        self.scrub_timer = QTimer(self)
        self.scrub_timer.setSingleShot(True)
        self.scrub_timer.setInterval(16)  # ~60fps, throttled to avoid flooding seeks
        self.scrub_timer.timeout.connect(self._apply_scrub_seek)


        # ----- Animations ----- #
        QApplication.processEvents()
        self.target_height = max(self.controls.sizeHint().height(), 60)
        self.controls.setMaximumHeight(self.target_height)

        self.animation = QPropertyAnimation(self.controls, b"maximumHeight")
        self.animation.setDuration(520)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuart)

        self.title_visible = True
        self.title_animation = QPropertyAnimation(self.title_bar, b"maximumHeight")
        self.title_animation.setDuration(520)
        self.title_animation.setEasingCurve(QEasingCurve.Type.OutQuart)
        self.title_animation.finished.connect(self._on_title_animation_finished)

        self.title_target_height = self.title_bar.height()
        self.title_bar.setMaximumHeight(self.title_target_height)

        # Hide timer
        hide_delay = self.settings.get("hide_delay", 2000)
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(hide_delay)
        self.hide_timer.timeout.connect(self.hide_controls)

        # ----- Mouse Tracking ----- #
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.setMouseTracking(True)
        self.video.video_widget.setMouseTracking(True)
        self.video.video_widget.installEventFilter(self)
        self.video.installEventFilter(self)
        self.video.video_widget.setAcceptDrops(True)
        self.video.setAcceptDrops(True)
        self.controls.setMouseTracking(True)
        self.controls.setAcceptDrops(True)
        self.title_bar.setAcceptDrops(True)
        self.title_bar.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)

        # ----- Space key for play/pause ----- #
        space_shortcut = QShortcut(Qt.Key.Key_Space, self)
        space_shortcut.activated.connect(self.toggle_play_pause)
        
        # ----- F key for fullscreen ----- #
        self.fullscreen_shortcut = QShortcut(Qt.Key.Key_F, self)
        self.fullscreen_shortcut.activated.connect(self.toggle_maximize)
        self.controls_shortcut = QShortcut(Qt.Key.Key_H, self)
        self.controls_shortcut.activated.connect(self.toggle_controls_visibility)

        # ----- Timer for timeline updates ----- #
        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update_timeline)

        self.was_playing = False

        # Apply startup preferences
        if self.settings.get("fullscreen_on_start", False):
            QTimer.singleShot(100, self.toggle_maximize)

        # ----- Connections to control panel ----- #
        self.controls.open_request.connect(self.load_video)
        self.controls.play_request.connect(self.toggle_play_pause)
        self.controls.stop_request.connect(self.stop)

        self.controls.timeline_pressed.connect(self.start_scrub)
        self.controls.timeline_released.connect(self.end_scrub)
        self.controls.timeline_moved.connect(self.preview_seek_pos)

        # unified track signal -> handler
        self.controls.track_vol_chg.connect(self.set_track_vol)
        self.controls.track_mute_chg.connect(self.set_track_mute)

        # Note: update_vol_ui connects per-thread in load_video_common,
        # so it fires exactly once per load (not twice).
        
        # Live progress for track extraction
        self.audio.track_extract_progress.connect(self.on_track_extract_progress)

        # ----- Connections to video player ----- #
        self.video.duration_changed.connect(self.update_dur)
        self.video.state_changed.connect(self.vid_state_chg)

    # ----- Event filter / UI hide logic ----- #
    def eventFilter(self, obj, event):
        if obj in (self.video, self.video.video_widget):
            if event.type() == QEvent.Type.DragEnter:
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    return True
            elif event.type() == QEvent.Type.Drop:
                urls = event.mimeData().urls()
                if urls:
                    file_path = urls[0].toLocalFile()
                    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ogg', '.mpeg', '.mpg', '.wmv', '.flv')
                    if file_path.lower().endswith(video_extensions):
                        self.load_video_from_path(file_path)
                        event.acceptProposedAction()
                        return True
                event.ignore()
                return True
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                self.toggle_maximize()
                return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    # Window edge always takes priority over a video click
                    global_pos = event.globalPosition().toPoint()
                    local_pos = self.mapFromGlobal(global_pos)
                    edge = self.get_resize_edge(local_pos)
                    if edge:
                        self.windowHandle().startSystemResize(edge)
                        return True
                    self.toggle_play_pause()
                    return True

        if event.type() == QEvent.Type.MouseMove:
            # Skip while the settings dialog is open - none of the player's
            # auto-hide/cursor logic applies while it's in front, and this
            # avoids a widgetAt() hit-test on every mouse move over it.
            if self.settings_dialog is not None and self.settings_dialog.isVisible():
                return False
            # Any mouse movement makes the cursor visible immediately.
            # The same auto-hide timer used for the control panel also
            # hides the cursor again when the player is playing.
            self._show_cursor_for_activity()
            self.reset_hide_timer()
            return False
        return super().eventFilter(obj, event)

    def _show_cursor_for_activity(self):
        """Reveal the cursor on mouse movement and restore the proper shape."""
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

        # Keep the resize cursor when the pointer is over a window edge.
        if not self.isMaximized() and not self.isFullScreen():
            edge = self.get_resize_edge(self.mapFromGlobal(QCursor.pos()))
            if edge in (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                return
            if edge in (Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                return
            if edge in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                return
            if edge in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
                self.setCursor(Qt.CursorShape.SizeVerCursor)
                return

        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_title_animation_finished(self):
        # QLayout honors minimumHeight, so restore it only after the show animation.
        if self.title_visible:
            self.title_bar.setMinimumHeight(self.title_target_height)
            self.title_bar.setMaximumHeight(self.title_target_height)
        else:
            self.title_bar.setMinimumHeight(0)
            self.title_bar.setMaximumHeight(0)

    def reset_hide_timer(self):
        pos = QCursor.pos()
        local_pos = self.mapFromGlobal(pos)
        reveal_zone = int(self.settings.get("mouse_reveal_zone", 60))
        near_top = reveal_zone > 0 and local_pos.y() <= reveal_zone
        near_bottom = reveal_zone > 0 and local_pos.y() >= self.height() - reveal_zone

        # The reveal zones work regardless of playback state.
        if (near_top or near_bottom) and (not self.controls_visible or not self.title_visible):
            self.show_controls()

        widget_under_mouse = QApplication.widgetAt(pos)
        over_ui = bool(widget_under_mouse and (
            self.controls.isAncestorOf(widget_under_mouse) or
            self.title_bar.isAncestorOf(widget_under_mouse) or
            widget_under_mouse in (self.controls, self.title_bar)
        ))

        # Keep controls available while the pointer is interacting with them.
        if over_ui or self.is_scrubbing:
            self.hide_timer.stop()
            return

        if local_pos.y() >= self.height() - reveal_zone and self.controls_visible:
            self.hide_timer.stop()
            return

        if not self.settings.get("auto_hide_controls", True) or not self.is_playing:
            self.hide_timer.stop()
            return

        self.hide_timer.start()

    def show_controls(self):
        if not self.controls_visible:
            self.animation.stop()
            self.animation.setStartValue(self.controls.maximumHeight())
            self.animation.setEndValue(self.target_height)
            self.animation.start()
            self.controls_visible = True

        if not self.title_visible:
            self.title_bar.setMinimumHeight(0)
            self.title_animation.stop()
            self.title_animation.setStartValue(self.title_bar.maximumHeight())
            self.title_animation.setEndValue(self.title_target_height)
            self.title_animation.start()
            self.title_visible = True

        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.hide_timer.stop()

    def hide_controls(self):
        # Skip while scrubbing or paused
        if self.is_scrubbing or not self.is_playing:
            return

        if not self.settings.get("auto_hide_controls", True):
            return

        # Skip if mouse is over the controls/title bar
        pos = QCursor.pos()
        widget_under_mouse = QApplication.widgetAt(pos)
        if widget_under_mouse and (self.controls.isAncestorOf(widget_under_mouse) or
                                   self.title_bar.isAncestorOf(widget_under_mouse) or
                                   widget_under_mouse == self.controls or widget_under_mouse == self.title_bar):
            return

        # Skip if mouse is near the bottom edge
        local_pos = self.mapFromGlobal(pos)
        if local_pos.y() > self.height() - 60:
            return

        # Even if the control panel is already hidden, the same timer must
        # still be able to hide the cursor after the activity timeout.
        # Previously this early return left the cursor visible forever after
        # the user moved the mouse while the panel was already hidden.
        if not self.controls_visible:
            if QApplication.overrideCursor() is None:
                QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
            else:
                QApplication.changeOverrideCursor(Qt.CursorShape.BlankCursor)
            self.setCursor(Qt.CursorShape.BlankCursor)
            self.hide_timer.stop()
            return

        self.animation.stop()
        self.animation.setStartValue(self.target_height)
        self.animation.setEndValue(0)
        self.animation.start()
        self.controls_visible = False

        self.title_bar.setMinimumHeight(0)
        self.title_animation.stop()
        self.title_animation.setStartValue(self.title_bar.maximumHeight())
        self.title_animation.setEndValue(0)
        self.title_animation.start()
        self.title_visible = False

        self.hide_timer.stop()
        # The cursor follows the same hide timeout as the control panel.
        # Keep an override cursor so child widgets cannot restore it while hidden.
        if QApplication.overrideCursor() is None:
            QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
        else:
            QApplication.changeOverrideCursor(Qt.CursorShape.BlankCursor)
        self.setCursor(Qt.CursorShape.BlankCursor)

    # ----- Volume UI handlers ----- #
    def set_track_vol(self, index: int, value: int):
        # Audio extracted with boost=5.0x, so setVolume(0.2) = 100% displayed volume.
        # Slider 0-100 maps to 0-max_volume%; gain = (value/100) * (max_volume/500)
        actual_volume_percent = int(value * self.max_volume / 100)
        gain = (value / 100.0) * (self.max_volume / 500.0)
        gain = max(0.0, min(1.0, gain))
        # Set audio manager volume for the given index
        self.audio.set_track_vol(index, gain)
        # Update the UI label for that track
        self.controls.set_track_vol_label(index, f"{actual_volume_percent}%")

        # Save volume if remember setting is enabled
        if self.settings.get("remember_volumes", False):
            self.settings["saved_volumes"][f"track_{index}"] = value
            self.queue_save_settings()

    def set_track_mute(self, index: int, muted: bool):
        if muted:
            self.audio.set_track_vol(index, 0.0)
        else:
            # Restore volume using correct gain calculation (audio pre-boosted 5.0x)
            try:
                _, slider, _ = self.controls._track_widgets[index]
                slider_value = slider.value()
                gain = (slider_value / 100.0) * (self.max_volume / 500.0)
                gain = max(0.0, min(1.0, gain))
                self.audio.set_track_vol(index, gain)
            except Exception:
                pass

    def apply_saved_volumes(self, saved_volumes):
        """Apply saved volumes to audio players and UI sliders"""
        for i in range(len(self.audio.audio_players)):
            track_key = f"track_{i}"
            if track_key in saved_volumes:
                volume = saved_volumes[track_key]
            
                # Apply to audio output (audio pre-boosted 5.0x)
                actual_percent = int(volume * self.max_volume / 100)
                gain = (volume / 100.0) * (self.max_volume / 500.0)
                gain = max(0.0, min(1.0, gain))
                self.audio.audio_outputs[i].setVolume(gain)
            
                # Update UI slider
                if i < len(self.controls._track_widgets):
                    _, slider, vol_label = self.controls._track_widgets[i]
                    slider.blockSignals(True)
                    slider.setValue(volume)
                    slider.blockSignals(False)
                
                    # Update label
                    display_percentage = int(volume * self.max_volume / 100)
                    vol_label.setText(f"{display_percentage}%")

    def update_vol_ui(self, num_audio_tracks):
        # create dynamic controls for N tracks
        orientation = self.settings.get("slider_orientation", "horizontal")
        self.controls.populate_track_controls(num_audio_tracks, orientation, self.max_volume)
        # adjust info text label naming for single track
        if num_audio_tracks == 1:
            try:
                label_widget, _, _ = self.controls._track_widgets[0]
                label_widget.setText("Volume:")
            except Exception:
                pass
        
        self.refresh_controls_target_height()

    # ----- Loading media and control ----- #
    def rebuild_recent_menu(self):
        """Refresh recent files quick-access menu in title bar"""
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        recent_files = self.settings.get("recent_files", [])
        if not recent_files:
            action = self.recent_menu.addAction("No recent files")
            action.setEnabled(False)
            return
        for path in recent_files:
            filename = os.path.basename(path)
            action = self.recent_menu.addAction(f"📹 {filename}")
            action.setToolTip(path)
            action.triggered.connect(lambda checked=False, p=path: self.load_video_from_path(p))
        self.recent_menu.addSeparator()
        self.recent_menu.addAction("🗑 Clear Recent Files", self.clear_recent_files)

    def clear_recent_files(self):
        self.settings["recent_files"] = []
        save_settings(self.settings)
        self.rebuild_recent_menu()

    def add_recent_file(self, file_path):
        recent_files = self.settings.get("recent_files", [])
        # Dedupe, move to front, cap list length
        recent_files = [p for p in recent_files if p != file_path]
        recent_files.insert(0, file_path)
        self.settings["recent_files"] = recent_files[:8]
        save_settings(self.settings)
        self.rebuild_recent_menu()

    def load_video(self):
        start_dir = self.settings.get("last_open_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", start_dir,
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.mpeg *.mpg *.wmv *.flv)"
        )
        if not file_path:
            return
        self.settings["last_open_dir"] = os.path.dirname(file_path)
        save_settings(self.settings)
        self.load_video_common(file_path)

    def load_video_common(self, file_path):
        # Cancel any thread still running from a previous load
        if self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.cancel()
            self.extraction_thread.wait()
            self.extraction_thread = None

        self.audio.stop_and_release_players()
        self.current_video_path = file_path
        self._detected_resolution = None
        self.add_recent_file(file_path)
        # Video loads immediately, independent of audio track detection
        self.video.set_media(self.current_video_path)
        self.video.set_video_muted()
        self.controls.set_info_text("Detecting audio tracks...")

        cache_limit_mb = self.settings.get("audio_cache_limit_mb", 2000)
        self.extraction_thread = AudioExtractorThread(file_path, self.audio, cache_limit_mb, self)
        self.extraction_thread.audio_tracks_detected.connect(self.update_vol_ui)
        self.extraction_thread.video_resolution_detected.connect(self.on_video_resolution_detected)
        self.extraction_thread.extraction_progress.connect(self.controls.set_info_text)
        self.extraction_thread.extraction_finished.connect(self.on_extraction_finished)
        self.extraction_thread.extraction_error.connect(self.on_extraction_error)
        self.extraction_thread.start()

    def on_video_resolution_detected(self, width, height):
        # Comes from the extraction thread's ffprobe call - no separate GUI-thread call needed
        self._detected_resolution = (width, height)
        
    def on_track_extract_progress(self, track_index, percent):
        # percent: max progress across all parallel track extractions
        if percent >= 100:
            self.controls.set_info_text("Audio extraction complete!")
            QTimer.singleShot(1000, lambda: self.controls.set_info_text(""))
        else:
            self.controls.set_info_text(f"Extracting audio tracks... {percent}%")

    def on_extraction_error(self, error_msg):
        # Audio failure shouldn't block video playback
        self.controls.set_info_text(f"Video loaded. Audio unavailable: {error_msg}")
        self.extraction_thread = None
        
    def on_extraction_finished(self, temp_files):
        # Video was already set up before extraction started; audio players
        # are created here since sources are set during setup_audio_players().
        if temp_files:
            self.audio.setup_audio_players()
            self.controls.set_info_text("")
        else:
            self.controls.set_info_text("Video loaded (no audio tracks). Click Play.")
            QTimer.singleShot(3000, lambda: self.controls.set_info_text(""))

        # Restore saved per-track volumes, if enabled
        if self.settings.get("remember_volumes", False):
            saved_volumes = self.settings.get("saved_volumes", {})
            QTimer.singleShot(250, lambda: self.apply_saved_volumes(saved_volumes))

        # Resize window to fit the video.
        #
        # NOT on Wayland: resizing this frameless top-level here permanently
        # breaks QVideoWidget's video scaling under the Qt 6 Wayland backend
        # (the video renders oversized and clipped until the window is moved
        # by hand). Tiling compositors reject the resize anyway, so nothing
        # is lost. X11 / Windows / macOS keep the auto-fit behaviour.
        if not self.isFullScreen() and not running_on_wayland():
            screen_geom = QApplication.primaryScreen().availableGeometry()
            screen_width, screen_height = screen_geom.width(), screen_geom.height()

            video_width, video_height = self._detected_resolution or (1280, 720)
            total_height = video_height + self.controls.sizeHint().height() + self.title_bar.height()
            total_width = video_width

            MARGIN_FACTOR = 0.9
            max_width = int(screen_width * MARGIN_FACTOR)
            max_height = int(screen_height * MARGIN_FACTOR)

            scale_w = max_width / total_width if total_width > 0 else 1.0
            scale_h = max_height / total_height if total_height > 0 else 1.0
            scale = min(scale_w, scale_h, 1.0)

            new_width = int(total_width * scale)
            new_height = int(total_height * scale)

            self.resize(new_width, new_height)
            self.center_window()

        if self.video.dur() > 0:
            self.update_dur(self.video.dur())

        self.extraction_thread = None

    def load_video_from_path(self, file_path):
        if not file_path or not os.path.exists(file_path):
            self.controls.set_info_text("File not found.")
            return
        self.load_video_common(file_path)

    # ----- Play/Pause/Stop and Sync ----- #
    def toggle_play_pause(self):
        # If no media, open dialog
        source = self.video.media_player.source()
        if source is None or source.isEmpty():
            self.load_video()
            return

        if not self.is_playing:
            self.play()
            self.controls._set_play_button_visual(True)
            self.is_playing = True
        else:
            self.pause()
            self.controls._set_play_button_visual(False)
            self.is_playing = False

    def play(self):
        self.video.play()
        self.audio.play()
        self.timer.start()
        # Hide timer only starts after mouse activity settles
        self.reset_hide_timer()

    def pause(self):
        self.video.pause()
        self.audio.pause()
        self.timer.stop()
        self.hide_timer.stop()
        # Pause doesn't reveal or hide the controls panel

    def stop(self):
        self.video.stop()
        self.audio.stop()
        self.timer.stop()
        self.hide_timer.stop()
        self.is_playing = False
        self.controls.timeline_slider.setValue(0)
        self.controls.set_timeline_label("00:00 / 00:00")
        self.show_controls()

    # ----- Scrubbing ----- #
    def update_dur(self, dur):
        dur = max(0, int(dur))
        self.controls.set_timeline_range(dur)
        self.controls.set_timeline_label(f"00:00 / {self.update_label(dur)}")

    def update_timeline(self):
        if self.is_scrubbing:
            return

        pos = self.video.pos()
        dur = self.controls.timeline_slider.maximum() or self.video.dur()
        # Some Qt backends report a position beyond their seekable range briefly;
        # keep the UI stable but never overwrite a valid end seek with a stale value.
        if self._pending_seek is not None and abs(pos - self._pending_seek) > 2000:
            self.video.set_pos(self._pending_seek)
            return
        if self._pending_seek is not None and abs(pos - self._pending_seek) <= 2000:
            self._pending_seek = None
        self.controls.set_timeline_value_blocked(min(pos, self.controls.timeline_slider.maximum()))
        self.controls.set_timeline_label(f"{self.update_label(pos)} / {self.update_label(dur)}")

        # Catch audio tracks that have silently stalled or drifted out of
        # sync with the video (independent decoders can do either over time).
        self._resync_tick_counter += 1
        if self._resync_tick_counter >= 10:  # ~every 500ms at the 50ms timer interval
            self._resync_tick_counter = 0
            self.audio.resync(pos, self.is_playing)

    def update_label(self, ms):
        seconds = ms // 1000
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02d}:{seconds:02d}"

    def refresh_controls_target_height(self):
        # Recalculate required height now that the contents changed
        QApplication.processEvents()
        new_target = self.controls.sizeHint().height()

        self.target_height = new_target

        # If controls are currently visible, apply immediately
        if self.controls_visible:
            self.controls.setMaximumHeight(new_target)

        # Update the animation end value so show_controls() opens to the right size
        self.animation.stop()
        self.animation.setEndValue(new_target)

    def preview_seek_pos(self, pos):
        dur = self.video.dur()
        self.controls.set_timeline_label(f"{self.update_label(pos)} / {self.update_label(dur)}")

        # Live scrub preview (YouTube-style), throttled to avoid flooding seeks
        self._pending_scrub_pos = pos
        if not self.scrub_timer.isActive():
            self.scrub_timer.start()

    def _apply_scrub_seek(self):
        if self.is_scrubbing and self._pending_scrub_pos is not None:
            self.video.set_pos(self._pending_scrub_pos)

    def start_scrub(self):
        self.was_playing = self.video.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.is_scrubbing = True
        self.video.pause()
        self.audio.pause()
        self.timer.stop()
        self.hide_timer.stop()

    def end_scrub(self):
        self.is_scrubbing = False
        self.scrub_timer.stop()
        self._pending_scrub_pos = None
        pos = self.controls.timeline_slider.value()

        pos = min(pos, max(0, self.controls.timeline_slider.maximum() - 1))
        self._pending_seek = pos
        self.video.set_pos(pos)
        self.audio.set_pos(pos)

        if self.was_playing:
            self.video.play()
            self.audio.play()
            self.timer.start()
            self.hide_timer.start()
        else:
            self.show_controls()

    def vid_state_chg(self, playing: bool):
        self.is_playing = playing
        self.controls._set_play_button_visual(playing)
        self.controls.play_button.setToolTip("Pause" if playing else "Play")
        if not playing:
            self.hide_timer.stop()

    def keyPressEvent(self, event):
        key = event.key()
        native = event.nativeVirtualKey() if hasattr(event, "nativeVirtualKey") else 0
        # Physical A/D keys on Windows, independent of keyboard layout.
        if native in (0x41, 0x44) or key in (Qt.Key.Key_A, Qt.Key.Key_D):
            delta = -5000 if native == 0x41 or key == Qt.Key.Key_A else 5000
            self.seek_relative(delta)
            event.accept()
            return
        # Arrow keys for seeking (← → equivalent to A/D)
        if key == Qt.Key.Key_Left:
            self.seek_relative(-5000)
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            self.seek_relative(5000)
            event.accept()
            return
        # Physical comma/period keys (< and >), independent of layout/Shift.
        if native in (0xBC, 0xBE) and not self.is_playing:
            self.seek_frame(-1 if native == 0xBC else 1)
            event.accept()
            return
        if key in (Qt.Key.Key_Less, Qt.Key.Key_Greater, Qt.Key.Key_Comma, Qt.Key.Key_Period) and not self.is_playing:
            self.seek_frame(-1 if key in (Qt.Key.Key_Less, Qt.Key.Key_Comma) else 1)
            event.accept()
            return
        super().keyPressEvent(event)

    def seek_relative(self, delta):
        dur = self.controls.timeline_slider.maximum() or self.video.dur()
        if dur <= 0:
            return
        pos = max(0, min(max(0, dur - 1), self.video.pos() + delta))
        self._pending_seek = pos
        self.video.set_pos(pos)
        self.audio.set_pos(pos)
        self.controls.set_timeline_value_blocked(pos)
        self.controls.set_timeline_label(f"{self.update_label(pos)} / {self.update_label(dur)}")

    def seek_frame(self, direction):
        # Qt Multimedia has no universal frame-step API; use a small timestamp step
        # while paused and force the player to remain paused.
        if self.is_playing:
            return
        step = 40
        dur = self.controls.timeline_slider.maximum() or self.video.dur()
        target = max(0, min(max(0, dur - 1), self.video.pos() + direction * step))
        self.video.set_pos(target)
        self.audio.set_pos(target)
        self.controls.set_timeline_value_blocked(target)
        self.controls.set_timeline_label(f"{self.update_label(target)} / {self.update_label(dur)}")
        QTimer.singleShot(30, self.video.pause)

    # ----- Resize/Drag window behavior ----- #
    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def toggle_maximize(self):
        """Animate between the saved window geometry and fullscreen."""
        if self._fullscreen_transitioning:
            return

        screen = QApplication.primaryScreen().geometry()
        duration = 150
        self._fullscreen_transitioning = True

        if self.isFullScreen():
            target = self.normal_geometry or QRectF(200, 100, 1600, 900).toRect()
            self.showNormal()
            self.setGeometry(screen)
            self.maximize_button.setText("□")
            self.window_transition = QPropertyAnimation(self, b"geometry", self)
            self.window_transition.setDuration(duration)
            self.window_transition.setStartValue(screen)
            self.window_transition.setEndValue(target)
            self.window_transition.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.window_transition.finished.connect(self._finish_window_transition)
            self.window_transition.start()
        else:
            self.normal_geometry = self.geometry()
            self.maximize_button.setText("▣")
            self.window_transition = QPropertyAnimation(self, b"geometry", self)
            self.window_transition.setDuration(duration)
            self.window_transition.setStartValue(self.geometry())
            self.window_transition.setEndValue(screen)
            self.window_transition.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.window_transition.finished.connect(self._enter_fullscreen_after_transition)
            self.window_transition.start()

    def _enter_fullscreen_after_transition(self):
        self.window_transition = None
        self.showFullScreen()
        self.maximize_button.setText("▣")
        self._fullscreen_transitioning = False
        self.raise_()
        # Keep an active title drag alive if fullscreen was reached by dragging.
        if self._title_dragging:
            self.dragPos = QCursor.pos()

    def _finish_window_transition(self):
        self.window_transition = None
        self._fullscreen_transitioning = False
        self.raise_()
        # Do not lose the mouse drag when leaving fullscreen from the title bar.
        if self._title_dragging:
            self.dragPos = QCursor.pos()
            self._drag_restore_pending = False

    def get_resize_edge(self, pos):
        # Determines if the position is near an edge.
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()

        if self.isMaximized() or self.isFullScreen():
            return 0

        # Widened edge-grab zone
        border = BORDER_SIZE
        on_left = x < border
        on_right = x > w - border
        on_top = y < border
        on_bottom = y > h - border

        if on_top and on_left:
            return Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        elif on_top and on_right:
            return Qt.Edge.TopEdge | Qt.Edge.RightEdge
        elif on_bottom and on_left:
            return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        elif on_bottom and on_right:
            return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        elif on_left:
            return Qt.Edge.LeftEdge
        elif on_right:
            return Qt.Edge.RightEdge
        elif on_top:
            return Qt.Edge.TopEdge
        elif on_bottom:
            return Qt.Edge.BottomEdge
        else:
            return 0

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self.get_resize_edge(event.pos())
            if edge != 0:
                self.dragPos = QPoint()
                self._title_dragging = False
                self.windowHandle().startSystemResize(edge)
                return

            title_bar_rect = self.title_bar.geometry()
            if title_bar_rect.contains(event.pos()):
                self.dragPos = event.globalPosition().toPoint()
                self._title_dragging = True
                self._drag_restore_pending = False
            else:
                self.dragPos = QPoint()
                self._title_dragging = False

    def start_drag_restore(self, cursor_global_pos):
        """
        Begin leaving fullscreen because the user is dragging the title bar
        down. The size shrink is eased over self._drag_restore_duration ms,
        but - unlike an earlier attempt with QPropertyAnimation/QTimer - there
        is only ONE place that ever calls setGeometry() during this: this
        class's own mouseMoveEvent, driven by real mouse-move events. That
        matches how v10 already updated the window during drags (which never
        crashed) and avoids a background QTimer racing with mouseMoveEvent to
        both touch window geometry in the same frame, which is what caused
        crashes on click/maximize before.
        """
        if self._fullscreen_transitioning:
            return

        target = self.normal_geometry or QRectF(200, 100, 1600, 900).toRect()
        self._drag_restore_start_size = self.size()
        self._drag_restore_target_size = target.size()

        self._fullscreen_transitioning = True
        self._drag_restore_pending = True
        self.showNormal()
        self.maximize_button.setText("□")

        # Anchor the window so the cursor stays under the title bar, using the
        # TARGET (normal) width - not the fullscreen width - so it doesn't
        # start off-center. Clamp so the window can't start off-screen left.
        target_w = self._drag_restore_target_size.width()
        start_x = max(0, cursor_global_pos.x() - target_w // 2)
        self.setGeometry(start_x, 0, self._drag_restore_start_size.width(), self._drag_restore_start_size.height())
        self.dragPos = cursor_global_pos

        self._drag_restore_elapsed = QElapsedTimer()
        self._drag_restore_elapsed.start()

    def _drag_restore_current_size(self):
        elapsed = self._drag_restore_elapsed.elapsed()
        t = min(1.0, elapsed / self._drag_restore_duration)
        eased = 1 - (1 - t) ** 3  # OutCubic, matches the rest of the app

        start = self._drag_restore_start_size
        end = self._drag_restore_target_size
        w = int(start.width() + (end.width() - start.width()) * eased)
        h = int(start.height() + (end.height() - start.height()) * eased)
        return w, h, t >= 1.0

    def mouseMoveEvent(self, event):
        global_pos = event.globalPosition().toPoint()

        if event.buttons() == Qt.MouseButton.LeftButton and self._title_dragging and self.dragPos != QPoint():
            if self._fullscreen_transitioning and self._drag_restore_pending:
                # Shrinking in progress: recompute size from elapsed time and
                # position from the cursor delta, then apply both in a single
                # setGeometry() call - this IS the animation tick, driven by
                # the mouse move that just arrived rather than a timer.
                new_pos = self.pos() + global_pos - self.dragPos
                w, h, done = self._drag_restore_current_size()
                self.setGeometry(new_pos.x(), new_pos.y(), w, h)
                self.dragPos = global_pos
                if done:
                    self._fullscreen_transitioning = False
                    self._drag_restore_pending = False
                return

            if self._fullscreen_transitioning:
                # Non-drag transition (e.g. F key) in flight - let it finish
                # untouched. _finish_window_transition() refreshes dragPos to
                # the current cursor position when it ends, so dragging
                # continues smoothly right after, no extra click needed.
                self.dragPos = global_pos
                return

            if self.isFullScreen():
                # Start restoring: size eases in over subsequent mouseMoveEvent
                # ticks above, position follows the cursor the same way.
                if global_pos.y() > 20:
                    self.start_drag_restore(global_pos)
                return

            new_pos = self.pos() + global_pos - self.dragPos

            # Dragging the title bar to the top enters fullscreen, but the same
            # mouse drag remains active after the animation completes.
            if new_pos.y() <= 0 and not self._fullscreen_transitioning:
                self._drag_restore_pending = False
                self.toggle_maximize()
                self.dragPos = global_pos
                return

            self.move(new_pos)
            self.dragPos = global_pos
            return

        self._show_cursor_for_activity()
        self.reset_hide_timer()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._fullscreen_transitioning and self._drag_restore_pending:
                # Mouse stopped moving before the shrink animation's duration
                # elapsed - snap straight to the final normal size/position
                # instead of leaving the window stuck at an intermediate size.
                target = self.normal_geometry or QRectF(200, 100, 1600, 900).toRect()
                pos = self.pos()
                self.setGeometry(pos.x(), pos.y(), target.width(), target.height())
                self._fullscreen_transitioning = False
                self._drag_restore_pending = False
            self.dragPos = QPoint()
            self._title_dragging = False
            self._drag_restore_pending = False
            if self.controls_visible or not self.is_playing:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    # ----- Settings window / settings API ----- #
    def queue_save_settings(self):
        """Debounced settings write - restarts a short timer instead of
        writing to disk immediately, so rapid changes (spinbox scrolling,
        slider drags) collapse into a single write."""
        self._settings_save_timer.start()

    def open_settings(self):
        """Open the dedicated settings window."""
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.refresh_values()
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def apply_theme(self, theme):
        """Apply and persist the selected application theme."""
        if theme == "light":
            QApplication.instance().setStyleSheet(LIGHT_THEME + """
QMenu { padding: 6px; border-radius: 10px; }
QMenu::item { padding: 8px 28px 8px 12px; border-radius: 6px; }
QMenu::item:selected { background: rgba(0, 173, 181, 0.18); }
QDialog#settings_dialog, QDialog#settings_dialog QWidget { background:#F5F7FA; color:#1A1F3A; }
QDialog#settings_dialog QGroupBox { border:1px solid #DDE2EA; border-radius:10px; margin-top:12px; padding:10px; font-weight:600; }
QDialog#settings_dialog QListWidget { background:#FFFFFF; border:1px solid #DDE2EA; border-radius:10px; padding:6px; }
QDialog#settings_dialog QListWidget::item { padding:10px; border-radius:7px; }
QDialog#settings_dialog QListWidget::item:selected { background:#EAF3FF; color:#006CC9; }
QDialog#settings_dialog QComboBox, QDialog#settings_dialog QSpinBox, QDialog#settings_dialog QDoubleSpinBox { background:#FFFFFF; border:1px solid #D0D6E0; border-radius:7px; padding:6px 10px; color:#1A1F3A; }
QDialog#settings_dialog QLineEdit { selection-background-color: transparent; selection-color: #1A1F3A; }
QDialog#settings_dialog QComboBox:focus, QDialog#settings_dialog QSpinBox:focus, QDialog#settings_dialog QDoubleSpinBox:focus { border-color:#0078D4; }

""")
        else:
            theme = "dark"
            QApplication.instance().setStyleSheet(DARK_THEME + """
QMenu { padding: 6px; border-radius: 10px; }
QMenu::item { padding: 8px 28px 8px 12px; border-radius: 6px; }
QMenu::item:selected { background: rgba(0, 173, 181, 0.22); }
QDialog#settings_dialog, QDialog#settings_dialog QWidget { background: #0A0E27; color: #E0E6FF; }
QDialog#settings_dialog QGroupBox { border:1px solid #252B4A; border-radius:10px; margin-top:12px; padding:10px; font-weight:600; }
QDialog#settings_dialog QListWidget { background:#0F1429; border:1px solid #252B4A; border-radius:10px; padding:6px; }
QDialog#settings_dialog QListWidget::item { padding:10px; border-radius:7px; }
QDialog#settings_dialog QListWidget::item:selected { background:rgba(0,217,255,0.16); color:#00D9FF; }
QDialog#settings_dialog QComboBox, QDialog#settings_dialog QSpinBox, QDialog#settings_dialog QDoubleSpinBox { background:#1A1F3A; border:1px solid #3A3F5D; border-radius:7px; padding:6px 10px; color:#E0E6FF; }
QDialog#settings_dialog QLineEdit { selection-background-color: transparent; selection-color: #E0E6FF; }
QDialog#settings_dialog QComboBox:focus, QDialog#settings_dialog QSpinBox:focus, QDialog#settings_dialog QDoubleSpinBox:focus { border-color:#00D9FF; }

""")

        self.settings["theme"] = theme
        self.queue_save_settings()

    def set_slider_orientation(self, orientation):
        """Change slider orientation between horizontal and vertical."""
        if orientation not in ("horizontal", "vertical"):
            orientation = "horizontal"

        self.settings["slider_orientation"] = orientation
        self.queue_save_settings()

        num_tracks = len(self.audio.audio_players)
        if num_tracks > 0:
            self.rebuild_volume_controls(num_tracks)

    def set_remember_volumes(self, enabled):
        """Enable or disable remembering per-track volume levels."""
        self.settings["remember_volumes"] = bool(enabled)
        self.queue_save_settings()

    def set_hide_delay(self, milliseconds):
        """Set the auto-hide delay in milliseconds."""
        milliseconds = max(100, min(60000, int(milliseconds)))
        self.settings["hide_delay"] = milliseconds
        self.queue_save_settings()
        self.hide_timer.setInterval(milliseconds)

    def set_mouse_reveal_zone(self, pixels):
        """Set the symmetric top/bottom mouse zone that reveals the control panel."""
        pixels = max(0, min(1000, int(pixels)))
        self.settings["mouse_reveal_zone"] = pixels
        self.queue_save_settings()

    def toggle_controls_visibility(self):
        if self.controls_visible or self.title_visible:
            self.hide_timer.stop()
            self.animation.stop()
            self.animation.setStartValue(self.controls.maximumHeight())
            self.animation.setEndValue(0)
            self.animation.start()
            self.title_bar.setMinimumHeight(0)
            self.title_animation.stop()
            self.title_animation.setStartValue(self.title_bar.maximumHeight())
            self.title_animation.setEndValue(0)
            self.title_animation.start()
            self.controls_visible = False
            self.title_visible = False
            if QApplication.overrideCursor() is None:
                QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
            self.setCursor(Qt.CursorShape.BlankCursor)
        else:
            self.show_controls()

    def set_auto_hide(self, enabled):
        """Enable or disable automatic hiding of playback controls."""
        enabled = bool(enabled)
        self.settings["auto_hide_controls"] = enabled
        self.queue_save_settings()
        if not enabled:
            self.show_controls()
            self.hide_timer.stop()

    def set_max_volume(self, max_vol):
        """Set maximum volume percentage."""
        max_vol = max(1, min(1000, int(max_vol)))
        self.settings["max_volume"] = max_vol
        self.max_volume = max_vol
        self.queue_save_settings()

        # Re-render the displayed percentages without changing slider positions.
        num_tracks = len(self.audio.audio_players)
        if num_tracks > 0:
            for i in range(num_tracks):
                try:
                    _, slider, _ = self.controls._track_widgets[i]
                    self.set_track_vol(i, slider.value())
                except Exception:
                    pass

    def set_fullscreen_on_start(self, enabled):
        """Enable or disable fullscreen at application startup."""
        self.settings["fullscreen_on_start"] = bool(enabled)
        self.queue_save_settings()

    def set_audio_cache_limit(self, limit_mb):
        """Set the size cap (MB) for the extracted-audio cache directory."""
        limit_mb = max(100, min(100000, int(limit_mb)))
        self.settings["audio_cache_limit_mb"] = limit_mb
        self.queue_save_settings()
        self.audio.prune_cache_dir(limit_mb)

    def clear_audio_cache_now(self):
        """Manually wipe the audio cache dir, keeping the currently loaded
        video's tracks (cleanup_temp_files/extract_audio_tracks would just
        recreate them, so a naive full wipe would kill live playback)."""
        currently_playing = set(self.audio.temp_files)
        try:
            for name in os.listdir(AUDIO_CACHE_DIR):
                path = os.path.join(AUDIO_CACHE_DIR, name)
                if path in currently_playing or not os.path.isfile(path):
                    continue
                try:
                    os.unlink(path)
                except Exception:
                    pass
        except Exception:
            pass

    def get_audio_cache_size_mb(self) -> float:
        """Total size of AUDIO_CACHE_DIR in MB, for the Settings display."""
        total = 0
        try:
            for name in os.listdir(AUDIO_CACHE_DIR):
                path = os.path.join(AUDIO_CACHE_DIR, name)
                if os.path.isfile(path):
                    total += os.path.getsize(path)
        except Exception:
            pass
        return total / (1024 * 1024)

    def export_video(self):
        """Export video with mixed audio tracks using ffmpeg (runs in background thread)"""
        # Check if a video is loaded
        if not self.current_video_path or not os.path.exists(self.current_video_path):
            QMessageBox.warning(self, "No Video Loaded", "Please load a video file before exporting.")
            return

        if self.export_thread and self.export_thread.isRunning():
            QMessageBox.warning(self, "Export In Progress", "An export is already running. Please wait for it to finish.")
            return

        # Check if there are audio tracks
        num_tracks = len(self.audio.audio_players)
        if num_tracks == 0:
            QMessageBox.warning(self, "No Audio Tracks", "The current video has no audio tracks to mix.")
            return

        # Get output file path from user
        default_name = os.path.splitext(os.path.basename(self.current_video_path))[0] + "_mixed.mp4"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video As",
            default_name,
            "MP4 Files (*.mp4);;MKV Files (*.mkv);;All Files (*.*)"
        )

        if not output_path:
            return  # User cancelled

        # Pause playback during export
        was_playing = self.is_playing
        if was_playing:
            self.pause()

        # Show progress message
        self.controls.set_info_text("Exporting video... This may take a while.")

        try:
            # Build ffmpeg command
            # Start with input video
            cmd = ["ffmpeg", "-i", self.current_video_path]

            # Add all audio track files as inputs (they are already extracted with 5.0x boost)
            for temp_file in self.audio.temp_files:
                cmd.extend(["-i", temp_file])

            # Build filter_complex for audio mixing with volume adjustments
            filter_parts = []
            for i in range(num_tracks):
                # Get the current volume from the slider (0-100)
                try:
                    _, slider, _ = self.controls._track_widgets[i]
                    slider_value = slider.value()
                    # Calculate the actual gain to apply
                    # In the player, we use: gain = (slider_value / 100.0) * (max_volume / 500.0)
                    # This is because the extracted audio is boosted 5x
                    # For export, we use the extracted WAV files (already boosted 5x),
                    # so we apply the same gain calculation
                    gain = (slider_value / 100.0) * (self.max_volume / 500.0)
                    # Clamp to reasonable range
                    gain = max(0.0, min(10.0, gain))
                except Exception:
                    gain = 1.0  # Default to normal volume if error

                # Audio input index is i+1 (video is 0, first audio is 1, etc.)
                filter_parts.append(f"[{i+1}:a]volume={gain}[a{i}]")

            # Mix all adjusted audio streams
            mix_inputs = "".join([f"[a{i}]" for i in range(num_tracks)])
            filter_parts.append(f"{mix_inputs}amix=inputs={num_tracks}:duration=longest[aout]")

            filter_complex = ";".join(filter_parts)

            # Add filter_complex to command
            cmd.extend(["-filter_complex", filter_complex])

            # Map video from first input and mixed audio
            cmd.extend([
                "-map", "0:v:0",    # First video stream from first input
                "-map", "[aout]",   # Mixed audio output
                "-c:v", "copy",     # Copy video codec (no re-encoding)
                "-c:a", "aac",      # Encode audio as AAC
                "-b:a", "320k",     # High quality audio bitrate
                "-progress", "pipe:1",  # For progress tracking
                "-y",               # Overwrite output file if exists
                output_path
            ])

            # Run ffmpeg in a background thread so the UI doesn't freeze
            duration_ms = self.video.dur()
            self.export_thread = ExportThread(cmd, output_path, duration_ms, self)
            self.export_thread.export_finished.connect(partial(self.on_export_finished, was_playing))
            self.export_thread.progress_changed.connect(self.on_export_progress)
            self.export_thread.export_cancelled.connect(self.on_export_cancelled)
            
            # Progress dialog with a Cancel button
            self.export_progress_dialog = QProgressDialog("Exporting video...", "Cancel", 0, 100, self)
            self.export_progress_dialog.setWindowTitle("Export Progress")
            self.export_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.export_progress_dialog.canceled.connect(self.cancel_export)
            self.export_progress_dialog.show()
            
            self.export_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{str(e)}")
            self.controls.set_info_text(f"Export error: {str(e)}")
            print("Export exception:", e)
            if was_playing:
                self.play()

    def on_export_progress(self, percent):
        if hasattr(self, 'export_progress_dialog') and self.export_progress_dialog:
            self.export_progress_dialog.setValue(percent)
        self.controls.set_info_text(f"Exporting... {percent}%")

    def on_export_cancelled(self):
        self.controls.set_info_text("Export cancelled.")

    def cancel_export(self):
        if self.export_thread and self.export_thread.isRunning():
            self.export_thread.cancel()
        if hasattr(self, 'export_progress_dialog') and self.export_progress_dialog:
            self.export_progress_dialog.close()
            self.export_progress_dialog = None

    def on_export_finished(self, was_playing, success, message):
        # Close the progress dialog
        if hasattr(self, 'export_progress_dialog') and self.export_progress_dialog:
            self.export_progress_dialog.close()
            self.export_progress_dialog = None
        if success:
            output_path = message
            QMessageBox.information(
                self,
                "Export Complete",
                f"Video exported successfully to:\n{output_path}"
            )
            self.controls.set_info_text(f"Export complete! Saved to:\n{os.path.basename(output_path)}")
        else:
            error_msg = message
            QMessageBox.critical(
                self,
                "Export Failed",
                f"FFmpeg export failed:\n{error_msg}"
            )
            self.controls.set_info_text("Export failed. Check console for details.")
            print("FFmpeg error:", error_msg)

        self.export_thread = None
        # Resume playback if it was playing before
        if was_playing:
            self.play()

    def rebuild_volume_controls(self, num_tracks):
        """Rebuild volume controls with current orientation"""
        current_volumes = []
        for _, slider, _ in self.controls._track_widgets:
            current_volumes.append(slider.value())
    
        orientation = self.settings.get("slider_orientation", "horizontal")
        self.controls.populate_track_controls(num_tracks, orientation, self.max_volume)
    
        for i, volume in enumerate(current_volumes):
            if i < len(self.controls._track_widgets):
                _, slider, _ = self.controls._track_widgets[i]
                slider.setValue(volume)
        
        self.refresh_controls_target_height()

    # ----- Cleanup ----- #
    def show_keyboard_shortcuts(self):
        """Show keyboard shortcuts help dialog"""
        shortcuts_text = """
Keyboard Shortcuts:

PLAYBACK:
  Space         - Play/Pause
  
NAVIGATION:
  A             - Seek backward 5 seconds
  D             - Seek forward 5 seconds
  ← →           - Seek backward/forward 5 seconds
  , (comma)     - Previous frame (while paused)
  . (period)    - Next frame (while paused)

WINDOW:
  F             - Fullscreen toggle
  H             - Hide/Show controls

ACTIONS:
  Export button - Export the current video with mixed audio tracks
  
MOUSE:
  Double-click  - Fullscreen toggle
  Click         - Play/Pause
  Drag edges    - Resize window
  Drag title    - Move window
  
DRAG & DROP:
  Drag video    - Load video file
"""
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    def closeEvent(self, event):
        if self.settings_dialog is not None:
            self.settings_dialog.close()
        self.timer.stop()
        self.hide_timer.stop()

        # Flush any debounced settings write (queue_save_settings) instead
        # of losing a change made just before quitting.
        if self._settings_save_timer.isActive():
            self._settings_save_timer.stop()
            save_settings(self.settings)

        if self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.cancel()
            self.extraction_thread.wait()

        if self.export_thread and self.export_thread.isRunning():
            # cancel() terminates the underlying ffmpeg subprocess; without
            # it, QThread.terminate() alone would kill the thread but leave
            # ffmpeg running as an orphaned background process.
            self.export_thread.cancel()
            if not self.export_thread.wait(3000):
                self.export_thread.terminate()
                self.export_thread.wait()

        self.video.stop()
        self.video.media_player.setVideoOutput(None)
        self.video.media_player.deleteLater()

        self.audio.cleanup_on_close()

        event.accept()

    def dragEnterEvent(self, event):
        """Accept drag events with video files"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle dropped files"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ogg', '.mpeg', '.mpg', '.wmv', '.flv')
            if file_path.lower().endswith(video_extensions):
                self.load_video_from_path(file_path)
            else:
                event.ignore()

# ------------------------------------- __main__ ------------------------------------- #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    theme = load_theme()

    if theme == "dark":
        app.setStyleSheet(DARK_THEME + """
QMenu { padding: 6px; border-radius: 10px; }
QMenu::item { padding: 8px 28px 8px 12px; border-radius: 6px; }
QMenu::item:selected { background: rgba(0, 173, 181, 0.22); }
QDialog#settings_dialog, QDialog#settings_dialog QWidget { background: #0A0E27; color: #E0E6FF; }
QDialog#settings_dialog QGroupBox { border:1px solid #252B4A; border-radius:10px; margin-top:12px; padding:10px; font-weight:600; }
QDialog#settings_dialog QListWidget { background:#0F1429; border:1px solid #252B4A; border-radius:10px; padding:6px; }
QDialog#settings_dialog QListWidget::item { padding:10px; border-radius:7px; }
QDialog#settings_dialog QListWidget::item:selected { background:rgba(0,217,255,0.16); color:#00D9FF; }
QDialog#settings_dialog QComboBox, QDialog#settings_dialog QSpinBox, QDialog#settings_dialog QDoubleSpinBox { background:#1A1F3A; border:1px solid #3A3F5D; border-radius:7px; padding:6px 10px; color:#E0E6FF; }
QDialog#settings_dialog QLineEdit { selection-background-color: transparent; selection-color: #E0E6FF; }
QDialog#settings_dialog QComboBox:focus, QDialog#settings_dialog QSpinBox:focus, QDialog#settings_dialog QDoubleSpinBox:focus { border-color:#00D9FF; }

""")
    else:
        app.setStyleSheet(LIGHT_THEME + """
QMenu { padding: 6px; border-radius: 10px; }
QMenu::item { padding: 8px 28px 8px 12px; border-radius: 6px; }
QMenu::item:selected { background: rgba(0, 173, 181, 0.18); }
QDialog#settings_dialog, QDialog#settings_dialog QWidget { background:#F5F7FA; color:#1A1F3A; }
QDialog#settings_dialog QGroupBox { border:1px solid #DDE2EA; border-radius:10px; margin-top:12px; padding:10px; font-weight:600; }
QDialog#settings_dialog QListWidget { background:#FFFFFF; border:1px solid #DDE2EA; border-radius:10px; padding:6px; }
QDialog#settings_dialog QListWidget::item { padding:10px; border-radius:7px; }
QDialog#settings_dialog QListWidget::item:selected { background:#EAF3FF; color:#006CC9; }
QDialog#settings_dialog QComboBox, QDialog#settings_dialog QSpinBox, QDialog#settings_dialog QDoubleSpinBox { background:#FFFFFF; border:1px solid #D0D6E0; border-radius:7px; padding:6px 10px; color:#1A1F3A; }
QDialog#settings_dialog QLineEdit { selection-background-color: transparent; selection-color: #1A1F3A; }
QDialog#settings_dialog QComboBox:focus, QDialog#settings_dialog QSpinBox:focus, QDialog#settings_dialog QDoubleSpinBox:focus { border-color:#0078D4; }

""")

    incoming_path = sys.argv[1] if len(sys.argv) > 1 else ""

    # ----- Single-instance check ----- #
    # When the .exe is registered as the handler for video files, double-
    # clicking a file in Explorer launches a brand new process each time.
    # To keep everything in one window, try to hand the path off to an
    # already-running instance first; only start a real UI if we're the
    # first (or only) instance.
    handoff_socket = QLocalSocket()
    handoff_socket.connectToServer(SINGLE_INSTANCE_KEY)
    if handoff_socket.waitForConnected(500):
        # Another instance is already running - forward the file path (if
        # any) to it and quit immediately instead of opening a 2nd window.
        if incoming_path:
            handoff_socket.write(os.path.abspath(incoming_path).encode("utf-8"))
            handoff_socket.flush()
            handoff_socket.waitForBytesWritten(1000)
        handoff_socket.disconnectFromServer()
        sys.exit(0)

    # We're the first instance: become the server that later launches will
    # talk to. removeServer() clears a stale socket left behind by a crash.
    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
    instance_server = QLocalServer()
    instance_server.listen(SINGLE_INSTANCE_KEY)

    # Prune any audio cache left behind by a crashed previous session (one
    # that never reached closeEvent's cleanup) back under the configured
    # limit. This is a prune, not a full wipe - a full wipe here would
    # defeat the point of the cache/size-limit feature by resetting it on
    # every single launch instead of just capping what accumulates.
    _startup_settings = load_settings()
    AudioManager().prune_cache_dir(_startup_settings.get("audio_cache_limit_mb", 2000))

    player = MainWindow()

    def _handle_incoming_connection():
        conn = instance_server.nextPendingConnection()
        if conn is None:
            return

        def _read_forwarded_path():
            data = bytes(conn.readAll()).decode("utf-8", errors="ignore").strip()
            if data:
                player.load_video_from_path(data)
            # Bring the existing window to the front instead of leaving a
            # new, separate window behind it.
            if player.isMinimized():
                player.showNormal()
            player.activateWindow()
            player.raise_()
            conn.disconnectFromServer()

        conn.readyRead.connect(_read_forwarded_path)

    instance_server.newConnection.connect(_handle_incoming_connection)

    if incoming_path:
        player.load_video_from_path(incoming_path)

    player.rebuild_recent_menu()
    player.show()
    player.activateWindow()
    player.raise_()
    player.setFocus()
    sys.exit(app.exec())
