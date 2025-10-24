import sys
import os
import tempfile
import ffmpeg
import subprocess
import json
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QPoint, QPropertyAnimation, QEvent, QEasingCurve, pyqtSignal, QObject, QRectF
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSlider, QWidget, QPushButton, QVBoxLayout, 
    QHBoxLayout, QFileDialog, QLabel, QSizePolicy, QMenu, QToolButton
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QShortcut, QCursor, QPainter

# Adding light mode/dark mode
appdata_dir = Path(os.getenv('APPDATA')) / "CrustyMediaPlayer"
appdata_dir.mkdir(exist_ok=True)
SETTINGS_FILE = appdata_dir / "settings.json"

def load_theme():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f).get("theme", "dark")
        except Exception:
            pass
    return "dark"

def save_theme(theme):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"theme": theme}, f)
    except Exception:
        pass

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

# The width in pixels where the window detects a resize drag on the border.
BORDER_SIZE = 8

# Force ffmpeg-python to use bundled ffmpeg.exe 
# Note: This path logic assumes an environment where ffmpeg.exe is adjacent to the script.
if getattr(sys, 'frozen', False):
    # Running as compiled .exe
    base_path = sys._MEIPASS
else:
    # Running as script
    base_path = os.path.dirname(__file__)

ffmpeg_path = os.path.join(base_path, 'ffmpeg.exe')
ffprobe_path = os.path.join(base_path, 'ffprobe.exe')

# Add to PATH
os.environ["PATH"] = base_path + os.pathsep + os.environ.get("PATH", "") 

# ------------------------------ Creating Video Manager ------------------------------ #
class VideoPlayer(QWidget):
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    state_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_widget)
        self.setLayout(layout)

        self.media_player.setVideoOutput(self.video_widget)

        self.media_player.positionChanged.connect(lambda pos: self.position_changed.emit(int(pos)))
        self.media_player.durationChanged.connect(lambda dur: self.duration_changed.emit(int(dur)))

        self.media_player.playbackStateChanged.connect(self.playback_state_changed)

    def playback_state_changed(self, state):
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.state_changed.emit(is_playing)

    def set_media(self, file_path: str):
        self.media_player.setSource(QUrl.fromLocalFile(file_path))

    def set_audio_output(self, audio_output):
        self.media_player.setAudioOutput(audio_output)

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

# ------------------------------ Creating Audio Manager ------------------------------ #

class AudioManager(QObject):
    audio_tracks_detected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.audio_player1 = QMediaPlayer() 
        self.audio_output1 = QAudioOutput() 
        self.audio_player1.setAudioOutput(self.audio_output1) 
        self.audio_output1.setVolume(0.25) 

        self.audio_player2 = QMediaPlayer() 
        self.audio_output2 = QAudioOutput() 
        self.audio_player2.setAudioOutput(self.audio_output2) 
        self.audio_output2.setVolume(0.25)

        self.temp_files = []

        self.ffprobe = "ffprobe"

    def cleanup_temp_files(self):
        for f in self.temp_files: 
            try: 
                os.unlink(f) 
            except Exception as e: 
                pass 
        self.temp_files = []

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
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            probe_data = json.loads(result.stdout) if result.stdout else {}
            streams = probe_data.get("streams", [])
            num = len(streams)
            self.audio_tracks_detected.emit(num)
            return num
        except Exception:
            return 0

    def extract_audio_tracks(self, file_path: str, max_tracks=2):
        # Extract up to `max_tracks` audio streams as WAV files, boosting volume like original
        self.cleanup_temp_files()
        num_audio_tracks = self.detect_audio_tracks(file_path)
        if num_audio_tracks == 0:
            return []

        for i in range(min(num_audio_tracks, max_tracks)):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_file.close()
            try:
                cmd = (
                    ffmpeg
                    .input(file_path)
                    .output(temp_file.name, map=f"0:a:{i}", af="volume=4.0", ac=2, ar="44100")
                    .overwrite_output()
                    .compile()
                )
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                self.temp_files.append(temp_file.name)
            except ffmpeg.Error:
                # stop if extraction fails
                break

        return self.temp_files

    def set_audio_src(self):
        if len(self.temp_files) >= 1:
            self.audio_player1.setSource(QUrl.fromLocalFile(self.temp_files[0]))
        if len(self.temp_files) >= 2:
            self.audio_player2.setSource(QUrl.fromLocalFile(self.temp_files[1]))

    def play(self):
        self.audio_player1.play()
        if len(self.temp_files) > 1:
            self.audio_player2.play()

    def pause(self):
        self.audio_player1.pause()
        if len(self.temp_files) > 1:
            self.audio_player2.pause()

    def stop(self):
        self.audio_player1.stop()
        if len(self.temp_files) > 1:
            self.audio_player2.stop()
    
    def set_pos(self, pos):
        self.audio_player1.setPosition(pos)
        if len(self.temp_files) > 1:
            self.audio_player2.setPosition(pos)

    def set_track1_vol(self, gain: float):
        self.audio_output1.setVolume(gain)

    def set_track2_vol(self, gain: float):
        self.audio_output2.setVolume(gain)

    def cleanup_on_close(self):
        self.stop()
        self.cleanup_temp_files()

# ------------------------------ Creating Control Panel ------------------------------ #

class ControlPanel(QWidget):
    open_request = pyqtSignal()
    play_request = pyqtSignal()
    stop_request = pyqtSignal()
    timeline_pressed = pyqtSignal()
    timeline_released = pyqtSignal()
    timeline_moved = pyqtSignal(int)
    track1_vol_chg = pyqtSignal(int)
    track2_vol_chg = pyqtSignal(int)

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
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal) 
        self.timeline_slider.setRange(0, 0)
        self.timeline_label = QLabel("00:00 / 00:00")

        # Info label
        self.info_label = QLabel("No File Loaded")

        # Audio track 1
        self.track1_label = QLabel("Track 1 Volume:")
        self.track1_slider = QSlider(Qt.Orientation.Horizontal)
        self.track1_slider.setRange(0, 100) 
        self.track1_slider.setValue(25) # Default 25% value = 100% audio gain
        self.track1_vol_label = QLabel("100%")

        # Audio track 2
        self.track2_label = QLabel("Track 2 Volume:")
        self.track2_slider = QSlider(Qt.Orientation.Horizontal)
        self.track2_slider.setRange(0, 100) 
        self.track2_slider.setValue(25) # Default 25% value = 100% audio gain
        self.track2_vol_label = QLabel("100%")

        # ----- Layouts ----- #
        controls_layout = QHBoxLayout() 
        controls_layout.addWidget(self.open_button) 
        controls_layout.addWidget(self.play_button) 
        controls_layout.addWidget(self.stop_button)

        volume_controls = QHBoxLayout()
        volume_controls.addWidget(self.track1_label)
        volume_controls.addWidget(self.track1_slider)
        volume_controls.addWidget(self.track1_vol_label) 
        volume_controls.addWidget(self.track2_label)
        volume_controls.addWidget(self.track2_slider)
        volume_controls.addWidget(self.track2_vol_label) 

        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(self.timeline_label)
        timeline_layout.addWidget(self.timeline_slider)

        # ----- Main Container ----- #
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(5)
        main_layout.addLayout(timeline_layout)
        main_layout.addWidget(self.info_label)
        main_layout.addLayout(volume_controls)
        main_layout.addLayout(controls_layout)

        # Connections
        self.open_button.clicked.connect(lambda: self.open_request.emit())
        self.play_button.clicked.connect(lambda: self.play_request.emit())
        self.stop_button.clicked.connect(lambda: self.stop_request.emit())

        self.timeline_slider.sliderPressed.connect(lambda: self.timeline_pressed.emit())
        self.timeline_slider.sliderReleased.connect(lambda: self.timeline_released.emit())
        self.timeline_slider.sliderMoved.connect(lambda pos: self.timeline_moved.emit(pos))

        self.track1_slider.valueChanged.connect(lambda vol: self.track1_vol_chg.emit(vol))
        self.track2_slider.valueChanged.connect(lambda vol: self.track2_vol_chg.emit(vol))

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

    def set_track1_vol_label(self, text):
        self.track1_vol_label.setText(text)

    def set_track2_vol_label(self,text):
        self.track2_vol_label.setText(text)

    def hide_track2_controls(self):
        self.track2_label.hide()
        self.track2_slider.hide()
        self.track2_vol_label.hide()

    def show_track2_controls(self):
        self.track2_label.show()
        self.track2_slider.show()
        self.track2_vol_label.show()

    def set_track1_label(self, text):
        self.track1_label.setText(text)

# ------------------------------- Creating Main Window ------------------------------- #

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ----- Window Setup ----- #
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint) 
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) 
        self.setGeometry(200, 100, 1600, 900) 
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # Core components
        self.video = VideoPlayer(self)
        self.audio = AudioManager(self)
        self.controls = ControlPanel(self)

        # Custom title bar
        self.title_bar = QWidget() 
        self.title_bar.setMinimumHeight(0)
        self.title_bar.setMaximumHeight(30) 
        self.title_label = QLabel("Crusty Media Player v1.0.0")
        self.title_label.setObjectName("titlelabel") 
        
        self.settings_button = QToolButton()
        self.settings_button.setText("*")
        self.settings_button.setFixedSize(30, 30)
        self.settings_button.setObjectName("settingsbutton")
        self.settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.settings_button.setArrowType(Qt.ArrowType.NoArrow)
 
        self.settings_menu = QMenu()
        self.settings_menu.addAction("Light Mode", lambda: self.apply_theme("light"))
        self.settings_menu.addAction("Dark Mode", lambda: self.apply_theme("dark"))
        self.settings_button.setMenu(self.settings_menu)

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

        # ----- Animations ----- #
        QApplication.processEvents() 
        self.target_height = max(self.controls.sizeHint().height(), 60)
        self.controls.setMaximumHeight(self.target_height)

        self.animation = QPropertyAnimation(self.controls, b"maximumHeight")
        self.animation.setDuration(350) # Animation duration in ms
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.title_visible = True
        self.title_animation = QPropertyAnimation(self.title_bar, b"maximumHeight")
        self.title_animation.setDuration(350)
        self.title_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.title_target_height = self.title_bar.height()
        self.title_bar.setMaximumHeight(self.title_target_height)

        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(3000) # Timer to hide controls in ms
        self.hide_timer.timeout.connect(self.hide_controls)

        # ----- Mouse Tracking ----- #
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.setMouseTracking(True)                       
        self.video.video_widget.setMouseTracking(True)          
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

        self.controls.track1_vol_chg.connect(self.set_track1_vol)
        self.controls.track2_vol_chg.connect(self.set_track2_vol)

        # ----- Connections to audio manager ----- #
        self.audio.audio_tracks_detected.connect(self.update_vol_ui)

        # ----- Connections to video player ----- #
        self.video.position_changed.connect(self.vid_pos_chg)
        self.video.duration_changed.connect(self.update_dur)
        self.video.state_changed.connect(self.vid_state_chg)

        # ----- Event filder and control visibility ----- #
    def eventFilter(self, obj, event):
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
            # Animate title bar
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

    # ----- Volume UI ----- #
    def set_track1_vol(self, value):
        gain = value / 100.0
        display_percentage = value * 4
        self.audio.set_track1_vol(gain)
        self.controls.set_track1_vol_label(f"{display_percentage}%")

    def set_track2_vol(self, value):
        gain = value / 100.0
        display_percentage = value * 4
        self.audio.set_track2_vol(gain)
        self.controls.set_track2_vol_label(f"{display_percentage}%")

    def update_vol_ui(self, num_audio_tracks):
        if num_audio_tracks == 1:
            self.controls.hide_track2_controls()
            self.controls.set_track1_label("Volume:")
        else:
            self.controls.show_track2_controls()
            self.controls.set_track1_label("Track 1 Volume:")

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

        extract = self.audio.extract_audio_tracks(file_path, max_tracks=2)
        if len(extract) < 1:
            self.controls.set_info_text("No audio tracks found in the selected file.")
            return

        self.video.set_media(file_path)
        self.video.set_video_muted()

        self.audio.set_audio_src()

        screen_geom = QApplication.primaryScreen().availableGeometry()
        screen_width, screen_height = screen_geom.width(), screen_geom.height()

        video_width, video_height = self.get_video_resolution(file_path)
        total_height = video_height + self.controls.sizeHint().height() + self.title_bar.height()
        total_width = video_width

        MARGIN_FACTOR = 0.9
        max_width = int(screen_width * MARGIN_FACTOR)
        max_height = int(screen_height * MARGIN_FACTOR)

        # Calculate scaling factor if video is larger than screen
        scale_w = max_width / total_width
        scale_h = max_height / total_height
        scale = min(scale_w, scale_h, 1.0)  # Don't upscale; only downscale

        new_width = int(total_width * scale)
        new_height = int(total_height * scale)

        if not self.isFullScreen():
            self.resize(new_width, new_height)
            self.center_window()

        self.controls.set_info_text(f"Loaded {len(self.audio.temp_files)} audio track(s). Click Play.")

        if self.video.dur() > 0:
            self.update_dur(self.video.dur())

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
            self.controls.play_button.setText("Pause")
            self.is_playing = True
        else:
            self.pause()
            self.controls.play_button.setText("Play")
            self.is_playing = False

    def play(self):
        self.video.play()
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

    def update_label(self, ms): 
        seconds = ms // 1000 
        minutes = seconds // 60 
        seconds %= 60 
        return f"{minutes:02d}:{seconds:02d}"
        
    def preview_seek_pos(self, pos):
        dur = self.video.dur()
        self.controls.set_timeline_label(f"{self.update_label(pos)} / {self.update_label(dur)}")

    def start_scrub(self):
        self.was_playing = self.video.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
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
    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def toggle_maximize(self):
        if self.isFullScreen():
            self.showNormal()
            self.maximize_button.setText("^")
        else:
            self.showFullScreen()
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
            edge = self.get_resize_edge(event.pos())
            if edge != 0: 
                self.dragPos = QPoint()
                # Starts the system resize handler 
                self.windowHandle().startSystemResize(edge) 
                return

            title_bar_rect = self.title_bar.geometry()
            if title_bar_rect.contains(event.pos()):
                self.dragPos = event.globalPosition().toPoint() 
            else:
                self.dragPos = QPoint()

            
    def mouseMoveEvent(self, event): 
        # Handles drag and resize cursor setting. The call to reset_hide_timer()
        # at the start is the key: it sets the default cursor (ArrowCursor) every time
        # the mouse moves, preventing
        #  stuck cursors, unless a boundary is immediately detected.
        self.reset_hide_timer()

        # 2. Dragging Check
        if event.buttons() == Qt.MouseButton.LeftButton and self.dragPos != QPoint(): 
            self.move(self.pos() + event.globalPosition().toPoint() - self.dragPos) 
            self.dragPos = event.globalPosition().toPoint() 
            return

        # 3. Resizing Cursor Check
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
        if theme == "light":
            QApplication.instance().setStyleSheet(LIGHT_THEME)
        else:
            QApplication.instance().setStyleSheet(DARK_THEME)
        save_theme(theme)

    # ----- Cleanup ----- #
    def closeEvent(self, event):
        self.stop()
        self.audio.cleanup_on_close()
        event.accept()

# ------------------------------------- __main__ ------------------------------------- #
if __name__ == "__main__": 
    app = QApplication(sys.argv) 
    theme = load_theme()

    if theme == "dark":
        app.setStyleSheet(DARK_THEME)
    else:
        app.setStyleSheet(LIGHT_THEME)

    player = MainWindow()

    if len(sys.argv) > 1:
        path = sys.argv[1]
        player.load_video_from_path(path)

    player.show() 
    sys.exit(app.exec())
