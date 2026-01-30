#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
import sys
import os
import tempfile
import subprocess
import json
from pathlib import Path
from urllib.parse import urlparse, unquote
from functools import partial

os.environ["LC_NUMERIC"] = "C"
is_wayland = os.environ.get("XDG_SESSION_TYPE") == "wayland"

import mpv
from mpv import MpvRenderContext, MpvGlGetProcAddressFn

from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation, QEvent, QEasingCurve, pyqtSignal, QObject
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSlider, QWidget, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QLabel, QSizePolicy, QMenu, QToolButton, QScrollArea, QStyle
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtGui import QShortcut, QCursor

# ----------------------------- Settings & Themes ----------------------------- #

def get_settings():
    app_name = "CrustyMediaPlayer"
    home = os.path.expanduser("~")
    settings_dir = os.path.join(home, ".config", app_name)
    os.makedirs(settings_dir, exist_ok=True)
    return os.path.join(settings_dir, "settings.json")

SETTINGS_FILE = get_settings()

def load_settings():
    """Load all settings from file"""
    default_settings = {
        "theme": "dark",
        "slider_orientation": "horizontal",  # or "vertical"
        "remember_volumes": False,
        "saved_volumes": {},  # Will store volume levels
        "hide_controls_on_start": False,
        "fullscreen_on_start": False
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                loaded = json.load(f)
                default_settings.update(loaded)
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

def save_theme(theme):
    settings = load_settings()
    settings["theme"] = theme
    save_settings(settings)

DARK_THEME = """
QMainWindow {
    background-color: #121212;
    border: 2px solid #00ADB5;
    border-radius: 8px;
}
QWidget {
    background-color: #121212;
    color: #EAEAEA;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
}
QLabel { color: #EAEAEA; }
QPushButton {
    background-color: #1F1F1F;
    border: 1px solid #2E2E2E;
    border-radius: 8px;
    padding: 6px 12px;
    color: #EAEAEA;
    font-weight: 500;
}
QPushButton:hover { background-color: #2E2E2E; }
QPushButton:pressed { background-color: #00ADB5; color: #000; }
QSlider::groove:horizontal {
    background: #333; height: 6px; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #00ADB5; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}
QSlider::sub-page:horizontal { background: #00ADB5; border-radius: 3px; }
QSlider::add-page:horizontal { background: #2A2A2A; border-radius: 3px; }

/* Vertical Slider Styles (match horizontal) */
QSlider::groove:vertical {
    background: #2A2A2A; width: 6px; border-radius: 3px;
}
QSlider::handle:vertical {
    background: #00ADB5; width: 14px; height: 14px; margin: 0 -5px; border-radius: 7px;
}
/* For vertical sliders, sub-page and add-page are swapped */
QSlider::sub-page:vertical { background: #2A2A2A; border-radius: 3px; }
QSlider::add-page:vertical { background: #00ADB5; border-radius: 3px; }

QWidget#title_bar {
    background-color: #1C1C1C;
    border-bottom: 1px solid #2E2E2E;
}

QLabel#titlelabel {
    color: #EAEAEA;
    font-weight: bold;
    padding-left: 10px;
}

QPushButton#settingsbutton,
QPushButton#minimizebutton,
QPushButton#maximizebutton,
QPushButton#closebutton {
    background: none;
    border: none;
    color: #EAEAEA;
    font-size: 14px;
}

QPushButton#settingsbutton:hover,
QPushButton#minimizebutton:hover,
QPushButton#maximizebutton:hover {
    color: #00ADB5;
}

/* Red hover for close button */
QPushButton#closebutton:hover {
    background-color: #E81123;
    color: white;
    border-radius: 4px;
}
"""

LIGHT_THEME = """
QMainWindow {
    background-color: #F7F7F7;
    border: 2px solid #0078D7;
    border-radius: 8px;
}
QWidget {
    background-color: #F7F7F7;
    color: #202020;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
}
QLabel { color: #202020; }
QPushButton {
    background-color: #E0E0E0;
    border: 1px solid #B0B0B0;
    border-radius: 8px;
    padding: 6px 12px;
    color: #202020;
    font-weight: 500;
}
QPushButton:hover { background-color: #D0D0D0; }
QPushButton:pressed { background-color: #0078D7; color: white; }
QSlider::groove:horizontal {
    background: #CCC; height: 6px; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #0078D7; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}
QSlider::sub-page:horizontal { background: #0078D7; border-radius: 3px; }
QSlider::add-page:horizontal { background: #CCC; border-radius: 3px; }

/* Vertical Slider Styles (match horizontal) */
QSlider::groove:vertical {
    background: #CCC; width: 6px; border-radius: 3px;
}
QSlider::handle:vertical {
    background: #0078D7; width: 14px; height: 14px; margin: 0 -5px; border-radius: 7px;
}
/* For vertical sliders, sub-page and add-page are swapped */
QSlider::sub-page:vertical { background: #CCC; border-radius: 3px; }
QSlider::add-page:vertical { background: #0078D7; border-radius: 3px; }

QWidget#title_bar {
    background-color: #EAEAEA;
    border-bottom: 1px solid #CCCCCC;
}

QLabel#titlelabel {
    color: #202020;
    font-weight: bold;
    padding-left: 10px;
}

QPushButton#settingsbutton,
QPushButton#minimizebutton,
QPushButton#maximizebutton,
QPushButton#closebutton {
    background: none;
    border: none;
    color: #202020;
    font-size: 14px;
}

QPushButton#settingsbutton:hover,
QPushButton#minimizebutton:hover,
QPushButton#maximizebutton:hover {
    color: #0078D7;
}

/* Red hover for close button */
QPushButton#closebutton:hover {
    background-color: #E81123;
    color: white;
    border-radius: 4px;
}
"""

# Border detection size
BORDER_SIZE = 8

# ------------------------------ Video Player ------------------------------ #
class VideoPlayer(QOpenGLWidget):
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    state_changed = pyqtSignal(bool)
    first_frame_ready = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.mpv = None
        self.ctx = None
        self._duration = 0
        self._is_playing = False
        self._current_file = None

        self.position_timer = QTimer(self)
        self.position_timer.setInterval(100)
        self.position_timer.timeout.connect(self._poll_position)

        # Set size policy to expand and fill available space
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

    # ---------------- OpenGL / mpv ---------------- #

    def initializeGL(self):
        # Ensure context is current (CRITICAL on Wayland)
        self.makeCurrent()

        self.mpv = mpv.MPV(
            vo="libmpv",
            hwdec="auto-safe",
            keep_open=True,
            idle=True,
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,
            ytdl=False,
            keepaspect=True,
        )

        @self.mpv.property_observer("time-pos")
        def _(name, value):
            if value is not None:
                self.position_changed.emit(int(value * 1000))

        @self.mpv.property_observer("duration")
        def _(name, value):
            if value is not None:
                self._duration = int(value * 1000)
                self.duration_changed.emit(self._duration)

        @self.mpv.property_observer("pause")
        def _(name, value):
            self._is_playing = not value
            self.state_changed.emit(self._is_playing)

        # -------- SAFE proc address wrapper -------- #
        # Create a proper ctypes callback function
        @MpvGlGetProcAddressFn
        def get_proc_address(_, name):
            # Keep name as bytes - Qt expects bytes
            if not isinstance(name, bytes):
                name = name.encode('utf-8')
            addr = self.context().getProcAddress(name)
            if addr is None:
                return 0  # MUST return 0, not None
            return int(addr)

        self.ctx = MpvRenderContext(
            self.mpv,
            api_type="opengl",
            opengl_init_params={
                "get_proc_address": get_proc_address
            }
        )

        # Set update callback to trigger repaints
        self.ctx.update_cb = self.on_mpv_update

    def on_mpv_update(self):
        """Called by MPV when it needs a repaint"""
        if self.isValid():
            self.update()

    def paintGL(self):
        if not self.ctx:
            return

        # Emit once when we actually have a real GL paint (prevents "huge then snap")
        if not getattr(self, "_first_frame_emitted", False):
            self._first_frame_emitted = True
            self.first_frame_ready.emit()

        # Get the actual framebuffer size (important for high DPI displays)
        ratio = self.devicePixelRatioF()
        w = int(self.width() * ratio)
        h = int(self.height() * ratio)

        self.ctx.render(
            flip_y=True,
            opengl_fbo={
                "fbo": self.defaultFramebufferObject(),
                "w": w,
                "h": h,
            },
        )

    def resizeGL(self, w, h):
        """Handle widget resize events"""
        if self.ctx:
            self.update()

    # ---------------- Media control ---------------- #

    def set_media(self, path):
        self._current_file = path
        self.mpv.play(path)
        self.mpv.pause = True
        self.position_timer.start()

    def set_video_muted(self):
        # Mute the video player so we only hear the extracted audio tracks
        if self.mpv:
            self.mpv.mute = True
            # Also set audio to 'no' to disable audio output entirely
            try:
                self.mpv.audio = 'no'
            except:
                pass

    def play(self):
        if self.mpv:
            self.mpv.pause = False

    def pause(self):
        if self.mpv:
            self.mpv.pause = True

    def stop(self):
        if self.mpv:
            self.mpv.command("stop")
            self.position_timer.stop()

    # ---------------- Timeline ---------------- #

    def _poll_position(self):
        if self.mpv:
            pos = self.mpv.time_pos
            if pos is not None:
                self.position_changed.emit(int(pos * 1000))

    def pos(self):
        if self.mpv and self.mpv.time_pos:
            return int(self.mpv.time_pos * 1000)
        return 0

    def dur(self):
        return self._duration

    def set_pos(self, ms):
        if self.mpv:
            self.mpv.seek(ms / 1000, reference="absolute")

    # ---------------- Cleanup ---------------- #

    def close(self):
        self.position_timer.stop()
        if self.mpv:
            try:
                self.mpv.terminate()
            except Exception:
                pass

# ------------------------------ Audio Manager (supports N tracks) ------------------------------ #
class AudioManager(QObject):
    audio_tracks_detected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # dynamic lists for arbitrary number of tracks
        self.audio_players = []   # list of mpv.MPV instances
        self.temp_files = []
        self.ffmpeg_subprocesses = []

        self.ffprobe = "ffprobe"

    def cleanup_temp_files(self):
        # stop players first
        for p in self.audio_players:
            try:
                p.terminate()
            except Exception:
                pass
        # remove temporary files
        for f in self.temp_files:
            try:
                os.unlink(f)
            except Exception:
                pass
        self.temp_files = []
        # clear players
        self.audio_players = []

    def detect_audio_tracks(self, file_path: str) -> int:
        # Use ffprobe to detect number of audio streams
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "json",
                file_path,
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            probe_data = json.loads(result.stdout) if result.stdout else {}
            streams = probe_data.get("streams", [])
            num = len(streams)
            self.audio_tracks_detected.emit(num)
            return num
        except Exception:
            return 0

    def extract_audio_tracks(self, file_path: str, max_tracks: int = None):
        # Extract all audio tracks (or up to max_tracks if provided) to WAV temp files. Returns list of temp file paths.
        self.cleanup_temp_files()
        num_audio_tracks = self.detect_audio_tracks(file_path)
        if num_audio_tracks == 0:
            return []

        total_to_extract = num_audio_tracks if max_tracks is None else min(num_audio_tracks, max_tracks)

        for i in range(total_to_extract):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_file.close()
            try:
                # Use ffmpeg to extract audio stream i, convert to 2ch 44100Hz WAV and boost gain
                cmd = [
                    "ffmpeg",
                    "-i", file_path,
                    "-map", f"0:a:{i}",
                    "-af", "volume=4.0",
                    "-ac", "2",
                    "-ar", "44100",
                    "-y",
                    temp_file.name
                ]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.ffmpeg_subprocesses.append(proc)
                proc.wait()
                self.temp_files.append(temp_file.name)
            except Exception:
                # stop if extraction fails for any stream
                break

        # create MPV players dynamically for each extracted file
        self.audio_players = []

        for path in self.temp_files:
            try:
                player = mpv.MPV(
                    video='no',
                    input_default_bindings='no',
                    input_vo_keyboard='no',
                    osc='no',
                    ytdl='no',
                    volume_max=100,  # Max volume is 100 (slider 200% = MPV 100)
                )
                # Start at volume 50 (matches slider default of 100 = normal volume)
                player.volume = 50
                player.play(path)
                player.pause = True
                self.audio_players.append(player)
            except Exception as e:
                print(f"Error creating audio player: {e}")
                pass

        return self.temp_files

    def set_audio_src(self):
        # Already set during extract. Keep for compatibility if needed.
        pass

    def play(self):
        for p in self.audio_players:
            try:
                p.pause = False
            except Exception:
                pass

    def pause(self):
        for p in self.audio_players:
            try:
                p.pause = True
            except Exception:
                pass

    def stop(self):
        for p in self.audio_players:
            try:
                p.command('stop')
            except Exception:
                pass

    def set_pos(self, pos):
        # pos in milliseconds
        for p in self.audio_players:
            try:
                p.seek(pos / 1000.0, reference='absolute')
            except Exception:
                pass

    def set_track_vol(self, index: int, gain: float):
        # New mapping:
        # gain is 0..1 where:
        #   0.0 = silent (MPV volume 0)
        #   0.5 = normal volume (MPV volume 50) 
        #   1.0 = +100% boost (MPV volume 100)
        if 0 <= index < len(self.audio_players):
            try:
                player = self.audio_players[index]
                
                # gain is 0..1, map to MPV volume 0..100
                mpv_volume = gain * 100  # 0..1 -> 0..100
                player.volume = mpv_volume
                
            except Exception as e:
                print(f"Error setting volume for track {index}: {e}")

    def cleanup_on_close(self):
        for p in self.ffmpeg_subprocesses:
            try:
                p.terminate()
            except Exception:
                pass

        for p in self.audio_players:
            try:
                p.terminate()
            except Exception:
                pass

        self.audio_players = []
        self.ffmpeg_subprocesses = []

# ------------------------------ Control Panel (dynamic track controls) ------------------------------ #
class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            value = QStyle.sliderValueFromPosition(
                self.minimum(),
                self.maximum(),
                int(event.position().x()),
                self.width()
            )
            self.setValue(value)
            self.sliderMoved.emit(value)
        super().mousePressEvent(event)

class ControlPanel(QWidget):
    open_request = pyqtSignal()
    play_request = pyqtSignal()
    stop_request = pyqtSignal()
    timeline_pressed = pyqtSignal()
    timeline_released = pyqtSignal()
    timeline_moved = pyqtSignal(int)
    # unified signal: (track_index, value)
    track_vol_chg = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Control buttons
        self.open_button = QPushButton("Open Media")
        self.play_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")
        for btn in [self.open_button, self.play_button, self.stop_button]:
            btn.setMinimumHeight(30)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Timeline slider
        self.timeline_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_label = QLabel("00:00 / 00:00")

        # Info label
        self.info_label = QLabel("No File Loaded")

        # The dynamic track controls area (scrollable if many tracks)
        self.track_controls_area = QScrollArea()
        self.track_controls_area.setWidgetResizable(True)
        self.track_container = QWidget()
        self.track_controls_layout = QVBoxLayout(self.track_container)
        self.track_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.track_controls_layout.setSpacing(6)
        self.track_container.setLayout(self.track_controls_layout)
        self.track_controls_area.setWidget(self.track_container)

        # ----- Layouts ----- #
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)

        volume_container_layout = QVBoxLayout()
        volume_container_layout.addWidget(QLabel("Audio Tracks:"))
        volume_container_layout.addWidget(self.track_controls_area)

        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(self.timeline_label)
        timeline_layout.addWidget(self.timeline_slider)

        # ----- Main Container ----- #
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(5)
        main_layout.addLayout(timeline_layout)
        main_layout.addWidget(self.info_label)
        main_layout.addLayout(volume_container_layout, stretch=1)  # Volume slider tile
        main_layout.addLayout(controls_layout, stretch=0)  # Button tile (directly below)

        # Connections
        self.open_button.clicked.connect(lambda: self.open_request.emit())
        self.play_button.clicked.connect(lambda: self.play_request.emit())
        self.stop_button.clicked.connect(lambda: self.stop_request.emit())

        self.timeline_slider.sliderPressed.connect(lambda: self.timeline_pressed.emit())
        self.timeline_slider.sliderReleased.connect(lambda: self.timeline_released.emit())
        self.timeline_slider.sliderMoved.connect(lambda pos: self.timeline_moved.emit(pos))

        # internal storage of controls for label updates
        self._track_widgets = []  # list of (label_widget, slider_widget, vol_label_widget)

    def clear_track_controls(self):
        # Remove existing controls
        for i in reversed(range(self.track_controls_layout.count())):
            item = self.track_controls_layout.itemAt(i)
            if item:
                w = item.widget()
                if w:
                    w.setParent(None)
        self._track_widgets = []

    def populate_track_controls(self, num_tracks: int, orientation="horizontal"):
        """Create N sliders/labels for audio tracks with specified orientation"""
        self.clear_track_controls()
        
        # Adjust scroll area behavior and sizing based on orientation
        if orientation == "vertical":
            # Vertical sliders don't need scrolling - they fill the space
            self.track_controls_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.track_controls_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            # Let the content size itself naturally - no constraints
            self.track_controls_area.setMinimumHeight(150)
            self.track_controls_area.setMaximumHeight(240) 
            self.track_controls_area.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum  # Take only what content needs
            )
        else:
            # Horizontal sliders might need scrolling if many tracks
            self.track_controls_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.track_controls_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            # Limit height for horizontal sliders
            self.track_controls_area.setMinimumHeight(0)
            self.track_controls_area.setMaximumHeight(200)
            self.track_controls_area.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred
            )
    
        # CHANGE THE CONTAINER LAYOUT BASED ON ORIENTATION
        # Clear and recreate the container with appropriate layout
        if orientation == "vertical":
            # For vertical sliders, arrange them horizontally (left to right)
            # So they're all visible without scrolling
        
            # Create a horizontal container for all the vertical sliders
            sliders_container = QWidget()
            sliders_layout = QHBoxLayout(sliders_container)
            sliders_layout.setContentsMargins(5, 5, 5, 5)
            sliders_layout.setSpacing(15)
            sliders_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
            for i in range(num_tracks):
                # Each slider column
                slider_widget = QWidget()
                slider_layout = QVBoxLayout(slider_widget)
                slider_layout.setContentsMargins(0, 0, 0, 0)
                slider_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                slider_layout.setSpacing(5)
            
                label = QLabel(f"Track {i+1}")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
                slider = ClickableSlider(Qt.Orientation.Vertical)
                slider.setRange(0, 200)  # 0-200% range
                slider.setValue(100)  # Start at 100 = 100% normal volume
                
                # Make slider expand but with constraints
                slider.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Preferred
                )
                slider.setMinimumHeight(100)
                slider.setMaximumHeight(200)  # Prevent too tall
            
                vol_label = QLabel("100%")
                vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
                slider_layout.addWidget(label)
                slider_layout.addWidget(slider, 1)  # stretch factor 1 to expand
                slider_layout.addWidget(vol_label)
            
                slider.valueChanged.connect(partial(self._on_track_slider_changed, i))
                sliders_layout.addWidget(slider_widget)
                self._track_widgets.append((label, slider, vol_label))
            
            # Add the horizontal container to the main vertical layout
            self.track_controls_layout.addWidget(sliders_container)
        
        else:
            # Horizontal sliders (original behavior)
            for i in range(num_tracks):
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
            
                label = QLabel(f"Track {i+1} Volume:")
                slider = ClickableSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, 200)  # 0-200% range
                slider.setValue(100)  # Start at 100 = 100% normal volume
                vol_label = QLabel("100%")
            
                row_layout.addWidget(label)
                row_layout.addWidget(slider)
                row_layout.addWidget(vol_label)
            
                slider.valueChanged.connect(partial(self._on_track_slider_changed, i))
                self.track_controls_layout.addWidget(row)
                self._track_widgets.append((label, slider, vol_label))
    
        # If no tracks, show a hint
        if num_tracks == 0:
            hint = QLabel("No audio tracks.")
            self.track_controls_layout.addWidget(hint)

    def _on_track_slider_changed(self, index: int, value: int):
        # Direct mapping: slider value = display percentage (0-200)
        display_percentage = value
        # update label
        try:
            _, _, vol_label = self._track_widgets[index]
            vol_label.setText(f"{display_percentage}%")
        except Exception:
            pass
        # emit unified signal
        self.track_vol_chg.emit(index, value)

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

# ------------------------------- Main Window ------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()

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
        self._pending_resize_path = None
        self.video.first_frame_ready.connect(self._on_first_video_frame)


        # Custom title bar
        self.title_bar = QWidget()
        self.title_bar.setMinimumHeight(0)
        self.title_bar.setMaximumHeight(30)
        self.title_bar.setObjectName("title_bar")
        self.title_label = QLabel("Crusty Media Player v1.3.0")
        self.title_label.setObjectName("titlelabel")

        self.settings_button = QToolButton()
        self.settings_button.setText("*")  # Changed from "*" to menu icon
        self.settings_button.setFixedSize(30, 30)
        self.settings_button.setObjectName("settingsbutton")
        self.settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.settings_button.setArrowType(Qt.ArrowType.NoArrow)

        self.settings_menu = QMenu()

        # File submenu
        file_menu = QMenu("File", self)
        self.export_action = file_menu.addAction("Export Video with Audio Mix...", self.export_video)
        self.settings_menu.addMenu(file_menu)

        # Appearance submenu
        appearance_menu = QMenu("Appearance", self)
        self.light_mode_action = appearance_menu.addAction("Light Mode", lambda: self.apply_theme("light"))
        self.light_mode_action.setCheckable(True)
        self.light_mode_action.setChecked(self.settings.get("theme") == "light")

        self.dark_mode_action = appearance_menu.addAction("Dark Mode", lambda: self.apply_theme("dark"))
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(self.settings.get("theme") == "dark")

        self.settings_menu.addMenu(appearance_menu)

        # Control Panel submenu
        control_panel_menu = QMenu("Control Panel", self)

        # Slider orientation
        self.horizontal_slider_action = control_panel_menu.addAction(
            "● Horizontal Sliders" if self.settings.get("slider_orientation") == "horizontal" else "○ Horizontal Sliders",
            lambda: self.set_slider_orientation("horizontal")
        )
        self.horizontal_slider_action.setCheckable(True)
        self.horizontal_slider_action.setChecked(self.settings.get("slider_orientation") == "horizontal")

        self.vertical_slider_action = control_panel_menu.addAction(
            "● Vertical Sliders" if self.settings.get("slider_orientation") == "vertical" else "○ Vertical Sliders",
            lambda: self.set_slider_orientation("vertical")
        )
        self.vertical_slider_action.setCheckable(True)
        self.vertical_slider_action.setChecked(self.settings.get("slider_orientation") == "vertical")

        control_panel_menu.addSeparator()

        # Remember volumes
        self.remember_volumes_action = control_panel_menu.addAction(
            "✓ Remember Volume Levels" if self.settings.get("remember_volumes") else "x Remember Volume Levels",
            self.toggle_remember_volumes
        )
        self.remember_volumes_action.setCheckable(True)
        self.remember_volumes_action.setChecked(self.settings.get("remember_volumes", False))

        control_panel_menu.addSeparator()

        # Startup behavior
        self.hide_controls_action = control_panel_menu.addAction(
            "✓ Hide Controls on Start" if self.settings.get("hide_controls_on_start") else "x Hide Controls on Start",
            self.toggle_hide_controls_on_start
        )
        self.hide_controls_action.setCheckable(True)
        self.hide_controls_action.setChecked(self.settings.get("hide_controls_on_start", False))

        self.fullscreen_start_action = control_panel_menu.addAction(
            "✓ Fullscreen on Start" if self.settings.get("fullscreen_on_start") else "x Fullscreen on Start",
            self.toggle_fullscreen_on_start
        )
        self.fullscreen_start_action.setCheckable(True)
        self.fullscreen_start_action.setChecked(self.settings.get("fullscreen_on_start", False))

        self.settings_menu.addMenu(control_panel_menu)
        self.settings_button.setMenu(self.settings_menu)

        # Apply startup preferences
        if self.settings.get("hide_controls_on_start", False):
            QTimer.singleShot(100, self.hide_controls)

        if self.settings.get("fullscreen_on_start", False):
            QTimer.singleShot(100, self.toggle_maximize)

        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setObjectName("closebutton")
        self.close_button.clicked.connect(self.close)

        self.minimize_button = QPushButton("—")
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.setObjectName("minimizebutton")
        self.minimize_button.clicked.connect(self.showMinimized)

        self.maximize_button = QPushButton("^")
        self.maximize_button.setFixedSize(30, 30)
        self.maximize_button.setObjectName("maximizebutton")
        self.maximize_button.clicked.connect(self.toggle_maximize)

        # ----- Layouts ----- #
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.settings_button)
        title_layout.addWidget(self.minimize_button)
        title_layout.addWidget(self.maximize_button)
        title_layout.addWidget(self.close_button)
        title_layout.setContentsMargins(5, 0, 5, 0)

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
        self.is_playing = False
        self.is_scrubbing = False
        self.controls_visible = True
        self.current_video_path = None  # Store the currently loaded video path


        # ----- Animations ----- #
        QApplication.processEvents()
        self.target_height = max(self.controls.sizeHint().height(), 200)
        self.controls.setMaximumHeight(self.target_height)
        self.controls.setMinimumHeight(0)

        self.animation = QPropertyAnimation(self.controls, b"maximumHeight")
        self.animation.setDuration(350)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.title_visible = True
        self.title_animation = QPropertyAnimation(self.title_bar, b"maximumHeight")
        self.title_animation.setDuration(350)
        self.title_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.title_target_height = self.title_bar.height()
        self.title_bar.setMaximumHeight(self.title_target_height)

        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(3000)
        self.hide_timer.timeout.connect(self.hide_controls)

        # ----- Mouse Tracking ----- #
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.setMouseTracking(True)
        self.video.setMouseTracking(True)
        self.video.installEventFilter(self)
        self.controls.setMouseTracking(True)
        self.title_bar.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)

        # ----- Space key for play/pause ----- #
        space_shortcut = QShortcut(Qt.Key.Key_Space, self)
        space_shortcut.activated.connect(self.toggle_play_pause)

        # ----- Timer for timeline updates ----- #
        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update_timeline)

        self.was_playing = False

        # ----- Connections to control panel ----- #
        self.controls.open_request.connect(self.load_video)
        self.controls.play_request.connect(self.toggle_play_pause)
        self.controls.stop_request.connect(self.stop)

        self.controls.timeline_pressed.connect(self.start_scrub)
        self.controls.timeline_released.connect(self.end_scrub)
        self.controls.timeline_moved.connect(self.preview_seek_pos)

        # unified track signal -> handler
        self.controls.track_vol_chg.connect(self.set_track_vol)

        # ----- Connections to audio manager ----- #
        self.audio.audio_tracks_detected.connect(self.update_vol_ui)

        # ----- Connections to video player ----- #
        self.video.position_changed.connect(self.vid_pos_chg)
        self.video.duration_changed.connect(self.update_dur)
        self.video.state_changed.connect(self.vid_state_chg)

    # ----- Event filter / UI hide logic ----- #
    def eventFilter(self, obj, event):
        if obj == self.video and event.type() == QEvent.Type.MouseButtonDblClick:
            self.toggle_maximize()
            return True

        if obj == self.video and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self.toggle_play_pause()
                return True

        if event.type() == QEvent.Type.MouseMove:
            self.reset_hide_timer()
            return False
        return super().eventFilter(obj, event)

    def reset_hide_timer(self):
        self.show_controls()

        widget_under_mouse = QApplication.widgetAt(QCursor.pos())
        if isinstance(widget_under_mouse, QSlider) or self.is_scrubbing:
            self.hide_timer.stop()
            return

        if self.is_playing:
            self.hide_timer.start()
        else:
            self.hide_timer.stop()

    def show_controls(self):
        if not self.controls_visible:
            self.animation.stop()
            self.animation.setStartValue(self.controls.maximumHeight())
            self.animation.setEndValue(self.target_height)
            self.animation.start()
            self.controls_visible = True

        if not self.title_visible:
            self.title_animation.stop()
            self.title_animation.setStartValue(self.title_bar.maximumHeight())
            self.title_animation.setEndValue(self.title_target_height)
            self.title_animation.start()
            self.title_visible = True

        self.setCursor(Qt.CursorShape.ArrowCursor)

    def hide_controls(self):
        if not self.controls_visible or self.is_scrubbing:
            return

        self.animation.stop()
        self.animation.setStartValue(self.target_height)
        self.animation.setEndValue(0)
        self.animation.start()
        self.controls_visible = False

        self.title_animation.stop()
        self.title_animation.setStartValue(self.title_target_height)
        self.title_animation.setEndValue(0)
        self.title_animation.start()
        self.title_visible = False

        self.hide_timer.stop()
        self.setCursor(Qt.CursorShape.BlankCursor)

    # ----- Volume UI handlers ----- #
    def refresh_controls_target_height(self):
        # Recalculate required height now that the contents changed
        QApplication.processEvents()
        new_target = max(self.controls.sizeHint().height(), 200)

        self.target_height = new_target

        # If controls are currently visible, apply immediately
        if self.controls_visible:
            self.controls.setMaximumHeight(new_target)

        # Update the animation end value so show_controls() opens to the right size
        self.animation.stop()
        self.animation.setEndValue(new_target)


    def set_track_vol(self, index: int, value: int):
        # Remap slider values to MPV volume:
        # Slider 0 = 0% = MPV 0 (silent)
        # Slider 100 = 100% = MPV 50 (normal/comfortable volume)
        # Slider 200 = 200% = MPV 100 (+100% boost)
        mpv_volume = value / 2.0  # Divide by 2 to map 0-200 slider to 0-100 MPV
        gain = value / 200.0  # Keep gain for compatibility (0-1 range)
        display_percentage = value  # Display shows slider value (0-200%)
        
        # Set audio manager volume for the given index
        self.audio.set_track_vol(index, mpv_volume / 100.0)  # Pass 0-1 range to audio manager
        # Update the UI label for that track
        self.controls.set_track_vol_label(index, f"{display_percentage}%")

        # Save volume if remember setting is enabled
        if self.settings.get("remember_volumes", False):
            self.settings["saved_volumes"][f"track_{index}"] = value
            save_settings(self.settings)

    def apply_saved_volumes(self, saved_volumes):
        """Apply saved volumes to audio players and UI sliders"""
        for i in range(len(self.audio.audio_players)):
            track_key = f"track_{i}"
            if track_key in saved_volumes:
                volume = saved_volumes[track_key]
                print(f"Applying saved volume for track {i}: {volume}")  # Debug
                
                # Apply to audio player
                gain = volume / 200.0  # Slider is 0-200
                self.audio.set_track_vol(i, gain)
                
                # Update UI slider
                if i < len(self.controls._track_widgets):
                    _, slider, vol_label = self.controls._track_widgets[i]
                    slider.blockSignals(True)
                    slider.setValue(volume)
                    slider.blockSignals(False)
                    
                    # Update label
                    display_percentage = volume  # Direct value is percentage
                    vol_label.setText(f"{display_percentage}%")

    def update_vol_ui(self, num_audio_tracks):
        # create dynamic controls for N tracks
        orientation = self.settings.get("slider_orientation", "horizontal")
        self.controls.populate_track_controls(num_audio_tracks, orientation)

        self.refresh_controls_target_height()

        # adjust info text label naming for single track
        if num_audio_tracks == 1:
            try:
                label_widget, _, _ = self.controls._track_widgets[0]
                label_widget.setText("Volume:")
            except Exception:
                pass

    # ----- Loading media and control ----- #
    def get_video_resolution(self, file_path):
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                file_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            data = json.loads(result.stdout)
            width = int(data["streams"][0]["width"])
            height = int(data["streams"][0]["height"])
            return width, height
        except Exception:
            return 1280, 720  # fallback default

    def load_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.mkv *.avi *.mov)"
        )
        if not file_path:
            return
        self.load_video_common(file_path)

    def load_video_common(self, file_path):
        self.current_video_path = file_path  # Store the current video path
        self.controls.set_info_text(f"Loading audio tracks from:\n{os.path.basename(file_path)}")

        self.audio.cleanup_temp_files()

        try:
            num_audio_tracks = self.audio.detect_audio_tracks(file_path)
        except Exception:
            self.controls.set_info_text("Error reading media file.")
            return

        self.update_vol_ui(num_audio_tracks)
        if num_audio_tracks == 0:
            self.controls.set_info_text("No audio tracks found in the selected file.")
            return

        # Extract ALL audio tracks (no hard cap)
        extract = self.audio.extract_audio_tracks(file_path)
        if len(extract) < 1:
            self.controls.set_info_text("No audio tracks found in the selected file.")
            return

        self.video.set_media(file_path)
        self.video.set_video_muted()

        self.audio.set_audio_src()
        
        # Set pending resize path - actual resize will happen on first frame
        self._pending_resize_path = file_path

        # Load saved volumes if setting is enabled (AFTER sliders are created)
        if self.settings.get("remember_volumes", False):
            saved_volumes = self.settings.get("saved_volumes", {})
            print(f"Loading saved volumes: {saved_volumes}")  # Debug
            # Wait for sliders to be created
            QTimer.singleShot(250, lambda: self.apply_saved_volumes(saved_volumes))

        self.controls.set_info_text(f"Loaded {len(self.audio.temp_files)} audio track(s). Click Play.")

        if self.video.dur() > 0:
            self.update_dur(self.video.dur())

    def load_video_from_path(self, file_path):
        if not file_path or not os.path.exists(file_path):
            self.controls.set_info_text("File not found.")
            return
        self.load_video_common(file_path)
    
    def _do_resize(self, width, height):
        """Helper to resize window - used with QTimer delay for Wayland"""
        self.setGeometry(self.x(), self.y(), width, height)
        self.resize(width, height)
        self.center_window()
        # Force window to activate/focus so Wayland applies the resize
        self.activateWindow()
        self.raise_()

    # ----- Play/Pause/Stop and Sync ----- #
    def toggle_play_pause(self):
        # If no media loaded, open file dialog
        if self.video._current_file is None:
            self.load_video()
            return

        if not self.is_playing:
            self.play()
            self.controls.play_button.setText("Pause")
            self.is_playing = True
        else:
            self.pause()
            self.controls.play_button.setText("Play")
            self.is_playing = False

    def play(self):
        self.video.play()
        # Sync audio to video position before playing
        if self.video.mpv and self.video.mpv.time_pos:
            video_pos_ms = int(self.video.mpv.time_pos * 1000)
            self.audio.set_pos(video_pos_ms)
        self.audio.play()
        self.timer.start()
        self.hide_timer.start()

    def pause(self):
        self.video.pause()
        self.audio.pause()
        self.timer.stop()
        self.hide_timer.stop()
        self.show_controls()

    def stop(self):
        self.video.stop()
        self.audio.stop()
        self.timer.stop()
        self.hide_timer.stop()
        self.is_playing = False
        self.controls.timeline_slider.setValue(0)
        self.controls.set_timeline_label("00:00 / 00:00")
        self.controls.play_button.setText("Play")
        self.show_controls()
    
    # ----- Scrubbing ----- #
    def update_dur(self, dur):
        self.controls.set_timeline_range(dur)
        self.controls.set_timeline_label(f"00:00 / {self.update_label(dur)}")

    def update_timeline(self):
        if self.is_scrubbing:
            return

        pos = self.video.pos()
        dur = self.video.dur()
        self.controls.set_timeline_value_blocked(pos)
        self.controls.set_timeline_label(f"{self.update_label(pos)} / {self.update_label(dur)}")
        
        # Periodically check for audio/video sync drift during playback
        # Only correct if drift is significant (> 200ms) to avoid audio glitches
        if self.is_playing and hasattr(self.audio, 'audio_players') and len(self.audio.audio_players) > 0:
            try:
                # Check first audio player as reference
                audio_player = self.audio.audio_players[0]
                if audio_player and audio_player.time_pos is not None:
                    video_pos_sec = pos / 1000.0
                    audio_pos_sec = audio_player.time_pos
                    drift = abs(video_pos_sec - audio_pos_sec)
                    
                    # If drift is more than 200ms, resync audio to video
                    if drift > 0.2:
                        self.audio.set_pos(pos)
            except Exception:
                pass  # Ignore sync errors


    def update_label(self, ms):
        seconds = ms // 1000
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02d}:{seconds:02d}"

    def preview_seek_pos(self, pos):
        dur = self.video.dur()
        self.controls.set_timeline_label(f"{self.update_label(pos)} / {self.update_label(dur)}")

    def start_scrub(self):
        self.was_playing = self.video._is_playing
        self.is_scrubbing = True
        self.video.pause()
        self.audio.pause()
        self.timer.stop()
        self.hide_timer.stop()

    def end_scrub(self):
        self.is_scrubbing = False
        pos = self.controls.timeline_slider.value()

        self.video.set_pos(pos)
        self.audio.set_pos(pos)

        if self.was_playing:
            self.video.play()
            # Re-sync audio to video position before resuming (in case there was any drift)
            if self.video.mpv and self.video.mpv.time_pos:
                video_pos_ms = int(self.video.mpv.time_pos * 1000)
                self.audio.set_pos(video_pos_ms)
            self.audio.play()
            self.timer.start()
            self.hide_timer.start()
        else:
            self.show_controls()

    def vid_pos_chg(self, pos):
        pass

    def vid_state_chg(self, playing: bool):
        self.is_playing = playing
        if not playing:
            self.show_controls()

    # ----- Resize/Drag window behavior ----- #
    def _on_first_video_frame(self):
        # Only resize when we explicitly requested it during load
        if not self._pending_resize_path:
            return

        path = self._pending_resize_path
        self._pending_resize_path = None

        # Make sure controls height is correct before computing final window size
        self.refresh_controls_target_height()
        self.resize_window_to_video(path)

    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def resize_window_to_video(self, file_path: str):
        screen_geom = QApplication.primaryScreen().availableGeometry()
        screen_width, screen_height = screen_geom.width(), screen_geom.height()

        video_width, video_height = self.get_video_resolution(file_path)

        # IMPORTANT: use the *current* target height, not sizeHint()
        controls_h = self.target_height
        title_h = self.title_bar.maximumHeight() if self.title_visible else self.title_target_height

        total_height = video_height + controls_h + title_h
        total_width = video_width

        MARGIN_FACTOR = 0.9
        max_width = int(screen_width * MARGIN_FACTOR)
        max_height = int(screen_height * MARGIN_FACTOR)

        scale_w = max_width / total_width if total_width > 0 else 1.0
        scale_h = max_height / total_height if total_height > 0 else 1.0
        scale = min(scale_w, scale_h, 1.0)

        new_width = int(total_width * scale)
        new_height = int(total_height * scale)

        if not self.isFullScreen():
            self.resize(new_width, new_height)
            self.center_window()

    def toggle_maximize(self):
        if self.isFullScreen():
            self.showNormal()
            if self.video.mpv:
                self.video.mpv.fullscreen = False
            self.maximize_button.setText("^")
        else:
            self.showFullScreen()
            if self.video.mpv:
                self.video.mpv.fullscreen = True
            self.maximize_button.setText("v")

    def get_resize_edge(self, pos):
        # Determines if the position is near an edge.
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()

        if self.isMaximized():
            return 0

        on_left = x < BORDER_SIZE
        on_right = x > w - BORDER_SIZE
        on_top = y < BORDER_SIZE
        on_bottom = y > h - BORDER_SIZE

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
            # Check if clicking on title bar for dragging
            if self.title_bar.geometry().contains(event.pos()):
                self.dragPos = event.globalPosition().toPoint()
            # Check if clicking on edge for resizing
            elif not self.isMaximized():
                edge = self.get_resize_edge(event.pos())
                if edge:
                    self.resizing = True
                    self.resize_edge = edge
                    self.resize_start_pos = event.globalPosition().toPoint()
                    self.resize_start_geometry = self.geometry()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Check for snap to fullscreen (drag to top of screen)
        if event.buttons() == Qt.MouseButton.LeftButton and self.dragPos != QPoint():
            new_pos = self.pos() + event.globalPosition().toPoint() - self.dragPos
        
            # Check if window is being dragged to top of screen
            if new_pos.y() <= 0 and not self.isFullScreen():
                self.showFullScreen()
                if self.video.mpv:
                    self.video.mpv.fullscreen = True
                self.maximize_button.setText("v")
                self.dragPos = QPoint()  # Stop dragging
                return
        
            self.move(new_pos)
            self.dragPos = event.globalPosition().toPoint()
            return
    
        self.reset_hide_timer()

        # Dragging Check
        if event.buttons() == Qt.MouseButton.LeftButton and self.dragPos != QPoint():
            self.move(self.pos() + event.globalPosition().toPoint() - self.dragPos)
            self.dragPos = event.globalPosition().toPoint()
            return

        # Resizing Cursor Check
        if not (event.buttons() & Qt.MouseButton.LeftButton) and not self.isMaximized():
            edge = self.get_resize_edge(event.pos())

            if edge == (Qt.Edge.TopEdge | Qt.Edge.LeftEdge) or edge == (Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif edge == (Qt.Edge.TopEdge | Qt.Edge.RightEdge) or edge == (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edge in [Qt.Edge.LeftEdge, Qt.Edge.RightEdge]:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edge in [Qt.Edge.TopEdge, Qt.Edge.BottomEdge]:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragPos = QPoint()

            # Ensure the cursor is restored to Arrow on release if controls are visible or we are paused/stopped.
            if self.controls_visible or not self.is_playing:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseReleaseEvent(event)

    # ----- Settings menu ----- #
    def apply_theme(self, theme):
        # Apply the chosen theme and remember it
        if theme == "dark":
            QApplication.instance().setStyleSheet(DARK_THEME)
            self.dark_mode_action.setChecked(True)
            self.light_mode_action.setChecked(False)
        else:
            QApplication.instance().setStyleSheet(LIGHT_THEME)
            self.light_mode_action.setChecked(True)
            self.dark_mode_action.setChecked(False)
    
        self.settings["theme"] = theme
        save_settings(self.settings)

    def set_slider_orientation(self, orientation):
        """Change slider orientation between horizontal and vertical"""
        self.settings["slider_orientation"] = orientation
        save_settings(self.settings)
    
        # Update checkmarks and text
        self.horizontal_slider_action.setChecked(orientation == "horizontal")
        self.horizontal_slider_action.setText(
            "● Horizontal Sliders" if orientation == "horizontal" else "○ Horizontal Sliders"
        )
    
        self.vertical_slider_action.setChecked(orientation == "vertical")
        self.vertical_slider_action.setText(
            "● Vertical Sliders" if orientation == "vertical" else "○ Vertical Sliders"
        )
    
        # Rebuild the volume controls
        num_tracks = len(self.audio.audio_players)
        if num_tracks > 0:
            self.rebuild_volume_controls(num_tracks)

    def toggle_remember_volumes(self):
        """Toggle the remember volumes setting"""
        current = self.settings.get("remember_volumes", False)
        new_value = not current
        self.settings["remember_volumes"] = new_value
        save_settings(self.settings)
        self.remember_volumes_action.setChecked(new_value)
        # Update text to show checkmark
        self.remember_volumes_action.setText(
            "✓ Remember Volume Levels" if new_value else "x Remember Volume Levels"
        )

    def toggle_hide_controls_on_start(self):
        """Toggle hide controls on start setting"""
        current = self.settings.get("hide_controls_on_start", False)
        new_value = not current
        self.settings["hide_controls_on_start"] = new_value
        save_settings(self.settings)
        self.hide_controls_action.setChecked(new_value)
        # Update text to show checkmark
        self.hide_controls_action.setText(
            "✓ Hide Controls on Start" if new_value else "x Hide Controls on Start"
        )

    def toggle_fullscreen_on_start(self):
        """Toggle fullscreen on start setting"""
        current = self.settings.get("fullscreen_on_start", False)
        new_value = not current
        self.settings["fullscreen_on_start"] = new_value
        save_settings(self.settings)
        self.fullscreen_start_action.setChecked(new_value)
        # Update text to show checkmark
        self.fullscreen_start_action.setText(
            "✓ Fullscreen on Start" if new_value else "x Fullscreen on Start"
        )

    def export_video(self):
        """Export video with mixed audio tracks using ffmpeg"""
        # Check if a video is loaded
        if not self.current_video_path or not os.path.exists(self.current_video_path):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Video Loaded", "Please load a video file before exporting.")
            return
        
        # Check if there are audio tracks
        num_tracks = len(self.audio.audio_players)
        if num_tracks == 0:
            from PyQt6.QtWidgets import QMessageBox
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
        QApplication.processEvents()
        
        try:
            # Build ffmpeg command
            # Start with input video
            cmd = ["ffmpeg", "-i", self.current_video_path]
            
            # Add all audio track files as inputs
            for temp_file in self.audio.temp_files:
                cmd.extend(["-i", temp_file])
            
            # Build filter_complex for audio mixing with volume adjustments
            filter_parts = []
            for i in range(num_tracks):
                # Get the current volume from the slider (0-200, where 100 = 100%)
                try:
                    _, slider, _ = self.controls._track_widgets[i]
                    slider_value = slider.value()
                    # Convert slider value to volume multiplier (slider 100 = 1.0x, 200 = 2.0x)
                    volume = slider_value / 100.0
                except Exception:
                    volume = 1.0  # Default to normal volume if error
                
                # Audio input index is i+1 (video is 0, first audio is 1, etc.)
                filter_parts.append(f"[{i+1}:a]volume={volume}[a{i}]")
            
            # Mix all adjusted audio streams
            mix_inputs = "".join([f"[a{i}]" for i in range(num_tracks)])
            filter_parts.append(f"{mix_inputs}amix=inputs={num_tracks}:duration=longest[aout]")
            
            filter_complex = ";".join(filter_parts)
            
            # Add filter_complex to command
            cmd.extend(["-filter_complex", filter_complex])
            
            # Map video from first input and mixed audio
            cmd.extend([
                "-map", "0:v",      # Video from first input
                "-map", "[aout]",   # Mixed audio output
                "-c:v", "copy",     # Copy video codec (no re-encoding)
                "-c:a", "aac",      # Encode audio as AAC
                "-b:a", "320k",     # High quality audio bitrate
                "-y",               # Overwrite output file if exists
                output_path
            ])
            
            # Run ffmpeg
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, 
                    "Export Complete", 
                    f"Video exported successfully to:\n{output_path}"
                )
                self.controls.set_info_text(f"Export complete! Saved to:\n{os.path.basename(output_path)}")
            else:
                from PyQt6.QtWidgets import QMessageBox
                error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                QMessageBox.critical(
                    self, 
                    "Export Failed", 
                    f"FFmpeg export failed:\n{error_msg}"
                )
                self.controls.set_info_text("Export failed. Check console for details.")
                print("FFmpeg error:", result.stderr)
        
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{str(e)}")
            self.controls.set_info_text(f"Export error: {str(e)}")
            print("Export exception:", e)
        
        finally:
            # Resume playback if it was playing before
            if was_playing:
                self.play()

    def rebuild_volume_controls(self, num_tracks):
        """Rebuild volume controls with current orientation"""
        # Save current volumes
        current_volumes = []
        for _, slider, _ in self.controls._track_widgets:
            current_volumes.append(slider.value())
    
        # Rebuild controls
        self.controls.populate_track_controls(num_tracks, self.settings.get("slider_orientation", "horizontal"))
    
        # Restore volumes
        for i, volume in enumerate(current_volumes):
            if i < len(self.controls._track_widgets):
                _, slider, _ = self.controls._track_widgets[i]
                slider.setValue(volume)
        
        self.refresh_controls_target_height()

    # ----- Cleanup ----- #
    def closeEvent(self, event):
        self.timer.stop()
        self.hide_timer.stop()

        self.video.stop()
        self.video.position_timer.stop()
        if self.video.mpv is not None:
            try:
                self.video.mpv.terminate()
            except Exception:
                pass

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
            # Check if it's a video file
            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.ogg', '.mpeg']
            if any(file_path.lower().endswith(ext) for ext in video_extensions):
                self.load_video_from_path(file_path)

# ------------------------------------- __main__ ------------------------------------- #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    theme = load_theme()

    if theme == "dark":
        app.setStyleSheet(DARK_THEME)
    else:
        app.setStyleSheet(LIGHT_THEME)

    player = MainWindow()

    def normalize_arg_to_path(arg: str) -> str:
        a = arg.strip().strip('"').strip("'")

        # Handle file:// URLs from %U / file managers
        if a.startswith("file://"):
            u = urlparse(a)
            a = unquote(u.path)

        # Common “oops I pasted punctuation” case (like .mp4.)
        if a.endswith(".") and Path(a[:-1]).exists():
            a = a[:-1]

        return a

    # Store the file path to load after window is shown
    file_to_load = None
    for raw in sys.argv[1:]:
        path = normalize_arg_to_path(raw)
        if Path(path).exists():
            file_to_load = path
            break

    # Show window first so OpenGL context initializes
    player.show()
    player.activateWindow()
    player.raise_()
    player.setFocus()
    
    # Now load the video after window is visible (and MPV is initialized)
    if file_to_load:
        # Use QTimer to ensure window is fully initialized
        QTimer.singleShot(100, lambda: player.load_video_from_path(file_to_load))
    
    sys.exit(app.exec())