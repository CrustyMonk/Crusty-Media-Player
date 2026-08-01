import sys
import os
import tempfile
import ffmpeg
import subprocess
import json
from pathlib import Path
from functools import partial

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QPoint, QPropertyAnimation, QEvent, QEasingCurve, pyqtSignal, QObject, QRectF, QThread
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSlider, QWidget, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QLabel, QSizePolicy, QMenu, QToolButton, QScrollArea, QStyle, QCheckBox
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QShortcut, QCursor, QPainter, QAction, QActionGroup, QActionGroup

# ----------------------------- Settings & Themes ----------------------------- #

def get_settings():
    app_name = "CrustyMediaPlayer"
    appdata = os.getenv("APPDATA")
    settings_dir = os.path.join(appdata, app_name)
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
        "recent_files": [],
        "last_open_dir": ""
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

/* Vertical Slider Styles */
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

/* Vertical Slider Styles */
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
BORDER_SIZE = 10  # Увеличил для лучшей чувствительности

# Force ffmpeg-python to use bundled ffmpeg.exe if present
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)

ffmpeg_path = os.path.join(base_path, 'ffmpeg.exe')
ffprobe_path = os.path.join(base_path, 'ffprobe.exe')

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
        # Включаем аппаратное ускорение
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
        # QVideoWidget рендерит видео через нативное окно, которое перехватывает
        # mouse/drag события ещё до Qt DnD-механизма. Делаем его "прозрачным" для
        # мыши, чтобы drag&drop события проваливались до VideoPlayer (self),
        # где dragEnterEvent/dropEvent уже реализованы и рабочие.
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

# ------------------------------ Audio Manager (supports N tracks) ------------------------------ #
class AudioManager(QObject):
    audio_tracks_detected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # dynamic lists for arbitrary number of tracks
        self.audio_players = []   # list of QMediaPlayer
        self.audio_outputs = []   # list of QAudioOutput
        self.temp_files = []
        self.ffmpeg_subprocesses = []

        self.ffprobe = "ffprobe"

    def cleanup_temp_files(self):
        # stop players first
        for p in self.audio_players:
            try:
                p.stop()
            except Exception:
                pass
        # remove temporary files
        for f in self.temp_files:
            try:
                os.unlink(f)
            except Exception:
                pass
        self.temp_files = []
        # clear players/outputs
        self.audio_players = []
        self.audio_outputs = []

    def probe_media(self, file_path: str):
        """Один вызов ffprobe вместо трёх: считает аудиодорожки и сразу берёт
        разрешение видео. Раньше это были отдельные ffprobe-запуски (детект
        аудио вызывался дважды, плюс отдельный запрос разрешения на GUI-потоке),
        что заметно тормозило открытие файла."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=index,codec_type,width,height",
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
            return audio_count, width, height
        except Exception:
            return 0, 1280, 720

    def detect_audio_tracks(self, file_path: str) -> int:
        # Тонкая обёртка над probe_media — раньше здесь был отдельный ffprobe-запуск.
        audio_count, _, _ = self.probe_media(file_path)
        self.audio_tracks_detected.emit(audio_count)
        return audio_count

    def extract_audio_tracks(self, file_path: str, num_audio_tracks: int = None, max_tracks: int = None):
        # Extract all audio tracks (or up to max_tracks if provided) to WAV temp files. Returns list of temp file paths.
        self.cleanup_temp_files()
        if num_audio_tracks is None:
            num_audio_tracks = self.detect_audio_tracks(file_path)
        if num_audio_tracks == 0:
            return []

        total_to_extract = num_audio_tracks if max_tracks is None else min(num_audio_tracks, max_tracks)

        # Запускаем ffmpeg для всех дорожек параллельно, а не по очереди —
        # суммарное время ожидания становится равно самой долгой дорожке,
        # а не сумме всех (важно именно для видео с несколькими дорожками).
        jobs = []  # (temp_path, process)
        for i in range(total_to_extract):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_file.close()
            try:
                # Use ffmpeg-python to extract audio stream i, convert to 2ch 44100Hz WAV and boost gain
                cmd = (
                    ffmpeg
                    .input(file_path)
                    .output(temp_file.name, map=f"0:a:{i}", af="volume=4.0", ac=2, ar="44100")
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
                jobs.append((temp_file.name, proc))
            except Exception:
                # stop launching more if one fails to start
                break

        for temp_path, proc in jobs:
            try:
                proc.wait()
                if proc.returncode == 0:
                    self.temp_files.append(temp_path)
            except Exception:
                pass

        return self.temp_files

    def setup_audio_players(self):
        """Create Qt audio objects in the GUI thread after extraction."""
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

    def set_audio_src(self):
        # Already set during extract (setSource). Keep for compatibility if needed.
        for i, path in enumerate(self.temp_files):
            try:
                self.audio_players[i].setSource(QUrl.fromLocalFile(path))
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

        for p in self.audio_players:
            try:
                p.stop()
                p.setAudioOutput(None)
                p.deleteLater()
            except Exception:
                pass

        for out in self.audio_outputs:
            try:
                out.deleteLater()
            except Exception:
                pass

        self.audio_players = []
        self.audio_outputs = []
        self.ffmpeg_subprocesses = []

# ------------------------------ Control Panel (dynamic track controls) ------------------------------ #
class ClickableSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dragging = False

    def _value_from_pos(self, pos):
        # Позиция может выходить за границы виджета (мышь зажата и уведена в сторону) —
        # зажимаем её в пределах виджета, чтобы значение оставалось в [minimum, maximum].
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

            # Захватываем мышь: теперь move/release будут приходить в этот
            # виджет, даже если курсор уйдёт за его пределы (как на YouTube).
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


# Новый класс для фонового извлечения
class AudioExtractorThread(QThread):
    # Сигналы для обновления UI
    extraction_finished = pyqtSignal(list)  # список путей к временным файлам
    extraction_progress = pyqtSignal(str)   # сообщение о прогрессе
    extraction_error = pyqtSignal(str)      # сообщение об ошибке
    audio_tracks_detected = pyqtSignal(int) # кол-во аудио-треков
    video_resolution_detected = pyqtSignal(int, int)  # (width, height), из того же ffprobe-вызова

    def __init__(self, file_path, audio_manager, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.audio_manager = audio_manager
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        # Останавливаем ffmpeg процессы, если они запущены
        for proc in self.audio_manager.ffmpeg_subprocesses:
            try:
                proc.terminate()
            except Exception:
                pass

    def run(self):
        try:
            # Шаг 1: один ffprobe-вызов — считаем аудиодорожки И разрешение видео разом.
            num_audio_tracks, width, height = self.audio_manager.probe_media(self.file_path)
            if self._is_cancelled:
                return
            self.audio_tracks_detected.emit(num_audio_tracks)
            self.video_resolution_detected.emit(width, height)

            if num_audio_tracks == 0:
                self.extraction_finished.emit([])
                return

            # Шаг 2: Извлекаем аудио (все дорожки параллельно, число уже известно из Шага 1)
            self.extraction_progress.emit("Extracting audio tracks...")
            temp_files = self.audio_manager.extract_audio_tracks(self.file_path, num_audio_tracks)
            
            if self._is_cancelled:
                # Если отменено, чистим за собой
                self.audio_manager.cleanup_temp_files()
                return

            if not temp_files:
                self.extraction_error.emit("Failed to extract audio tracks.")
                return

            # Шаг 3: Настраиваем плееры для аудио (это быстро, можно оставить в основном потоке)
            # Но мы передадим список файлов в основной поток через сигнал
            self.extraction_finished.emit(temp_files)

        except Exception as e:
            if not self._is_cancelled:
                self.extraction_error.emit(f"Extraction failed: {str(e)}")

# Фоновый поток экспорта: раньше финальный ffmpeg-рендер запускался через
# subprocess.run() прямо в GUI-потоке и полностью замораживал окно на всё
# время экспорта (никакой перерисовки, drag/resize, ничего).
class ExportThread(QThread):
    export_finished = pyqtSignal(bool, str)  # (success, output_path_or_error_message)

    def __init__(self, cmd, output_path, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self.output_path = output_path

    def run(self):
        try:
            result = subprocess.run(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode == 0:
                self.export_finished.emit(True, self.output_path)
            else:
                error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                self.export_finished.emit(False, error_msg)
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
        # Set default size policy to prevent expanding into buttons
        self.track_controls_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.track_controls_area.setMaximumHeight(200)  # Default max height
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

    def populate_track_controls(self, num_tracks: int, orientation="horizontal"):
        # Create N sliders/labels for audio tracks with specified orientation
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
                slider.setValue(25)
                slider.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
                slider.setMinimumHeight(100)
                slider.setMaximumHeight(200)
                
                vol_label = QLabel("100%")
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
        else:
            # Horizontal sliders (original)
            for i in range(num_tracks):
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                label = QLabel(f"Track {i+1} Volume:")
                slider = ClickableSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, 100)
                slider.setValue(25)
                vol_label = QLabel("100%")
                mute_box = QCheckBox("Mute")
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
        # Mirror old display semantics: slider value * 4 = displayed percentage
        display_percentage = value * 4
        # update label
        try:
            _, _, vol_label = self._track_widgets[index]
            vol_label.setText(f"{display_percentage}%")
        except Exception:
            pass
        # emit unified signal
        self.track_vol_chg.emit(index, value)

    def _on_track_mute_toggled(self, index: int, muted: bool):
        # Пока дорожка замьючена, её слайдер отключён — так громкость не
        # "спорит" сама с собой между звуком слайдера и состоянием mute.
        try:
            _, slider, _ = self._track_widgets[index]
            slider.setEnabled(not muted)
        except Exception:
            pass
        self.track_mute_chg.emit(index, muted)

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
        self.extraction_thread = None
        self.export_thread = None
        self.normal_geometry = None  # Для сохранения геометрии окна

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
        self.title_bar.setMinimumHeight(0)
        self.title_bar.setMaximumHeight(30)
        self.title_label = QLabel("Crusty Media Player v1.4.0")
        self.title_label.setObjectName("titlelabel")

        self.settings_button = QToolButton()
        self.settings_button.setText("*")
        self.settings_button.setFixedSize(30, 30)
        self.settings_button.setObjectName("settingsbutton")
        self.settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.settings_button.setArrowType(Qt.ArrowType.NoArrow)

        self.settings_menu = QMenu()

        # File submenu
        file_menu = QMenu("File", self)
        self.export_action = file_menu.addAction("Export Video with Audio Mix...", self.export_video)
        self.recent_menu = QMenu("Open Recent", self)
        file_menu.addMenu(self.recent_menu)
        self.settings_menu.addMenu(file_menu)
        self.rebuild_recent_menu()

        # Appearance submenu
        appearance_menu = QMenu("Appearance", self)
        self.light_mode_action = appearance_menu.addAction("Light Mode", lambda: self.apply_theme("light"))
        self.light_mode_action.setCheckable(True)
        
        self.dark_mode_action = appearance_menu.addAction("Dark Mode", lambda: self.apply_theme("dark"))
        self.dark_mode_action.setCheckable(True)
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        self.theme_action_group.addAction(self.light_mode_action)
        self.theme_action_group.addAction(self.dark_mode_action)
        
        # Устанавливаем правильное состояние галочек
        if self.settings.get("theme") == "light":
            self.light_mode_action.setChecked(True)
            self.dark_mode_action.setChecked(False)
        else:
            self.light_mode_action.setChecked(False)
            self.dark_mode_action.setChecked(True)
            
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
        
        # Auto hide controls
        self.auto_hide_action = control_panel_menu.addAction(
            "✓ Auto-hide Controls" if self.settings.get("auto_hide_controls", True) else "x Auto-hide Controls",
            self.toggle_auto_hide
        )
        self.auto_hide_action.setCheckable(True)
        self.auto_hide_action.setChecked(self.settings.get("auto_hide_controls", True))

        hide_delay_menu = QMenu("Hide Delay", self)
        self.hide_delay_group = QActionGroup(self)
        self.hide_delay_group.setExclusive(True)
        self.hide_delay_actions = {}
        for ms, label in [(1000, "1 second"), (2000, "2 seconds"), (3000, "3 seconds"), (5000, "5 seconds"), (10000, "10 seconds")]:
            action = hide_delay_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.settings.get("hide_delay", 2000) == ms)
            action.triggered.connect(lambda checked=False, value=ms: self.set_hide_delay(value))
            self.hide_delay_group.addAction(action)
            self.hide_delay_actions[ms] = action
        control_panel_menu.addMenu(hide_delay_menu)

        # Startup behavior
        self.fullscreen_start_action = control_panel_menu.addAction(
            "✓ Fullscreen on Start" if self.settings.get("fullscreen_on_start") else "x Fullscreen on Start",
            self.toggle_fullscreen_on_start
        )
        self.fullscreen_start_action.setCheckable(True)
        self.fullscreen_start_action.setChecked(self.settings.get("fullscreen_on_start", False))

        self.settings_menu.addMenu(control_panel_menu)
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
        self.current_video_path = None  # Store the currently loaded video path
        self._detected_resolution = None
        self._pending_seek = None
        self.mouse_in_controls = False  # Флаг для отслеживания наведения на контролы

        # ----- Живой предпросмотр кадра при перетаскивании ползунка ----- #
        self._pending_scrub_pos = None
        self.scrub_timer = QTimer(self)
        self.scrub_timer.setSingleShot(True)
        self.scrub_timer.setInterval(16)  # ~60 обновлений/сек — плавно, но без флуда seek-ами
        self.scrub_timer.timeout.connect(self._apply_scrub_seek)


        # ----- Animations ----- #
        QApplication.processEvents()
        self.target_height = max(self.controls.sizeHint().height(), 60)
        self.controls.setMaximumHeight(self.target_height)

        self.animation = QPropertyAnimation(self.controls, b"maximumHeight")
        self.animation.setDuration(350)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.title_visible = True
        self.title_animation = QPropertyAnimation(self.title_bar, b"maximumHeight")
        self.title_animation.setDuration(350)
        self.title_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.title_target_height = self.title_bar.height()
        self.title_bar.setMaximumHeight(self.title_target_height)

        # Настройка таймера скрытия
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

        # Примечание: update_vol_ui подключается к каждому AudioExtractorThread
        # индивидуально в load_video_common — так он вызывается ровно один раз
        # на загрузку, а не дважды (раньше self.audio.audio_tracks_detected тоже
        # был подключён здесь напрямую, и оба сигнала срабатывали на одно и то же
        # событие, пересоздавая виджеты дорожек лишний раз).

        # ----- Connections to video player ----- #
        self.video.position_changed.connect(self.vid_pos_chg)
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
                    # Край окна всегда имеет приоритет над кликом по видео.
                    global_pos = event.globalPosition().toPoint()
                    local_pos = self.mapFromGlobal(global_pos)
                    edge = self.get_resize_edge(local_pos)
                    if edge:
                        self.windowHandle().startSystemResize(edge)
                        return True
                    self.toggle_play_pause()
                    return True

        if event.type() == QEvent.Type.MouseMove:
            self.reset_hide_timer()
            return False
        return super().eventFilter(obj, event)

    def reset_hide_timer(self):
        # Показываем контролы всегда при движении мыши, если они скрыты
        if not self.controls_visible or not self.title_visible:
            self.show_controls()

        # Проверяем, находится ли мышь над виджетами, которые должны удерживать панель
        pos = QCursor.pos()
        widget_under_mouse = QApplication.widgetAt(pos)

        # Если мышь над панелью управления, ползунком или мы скраббим - не прячем
        if (widget_under_mouse and (self.controls.isAncestorOf(widget_under_mouse) or
            self.title_bar.isAncestorOf(widget_under_mouse) or
            widget_under_mouse == self.controls or widget_under_mouse == self.title_bar)
            ) or self.is_scrubbing:
            self.hide_timer.stop()
            return

        # Если мышь в нижней части окна (последние 60 пикселей)
        local_pos = self.mapFromGlobal(pos)
        if local_pos.y() > self.height() - 60:
            self.hide_timer.stop()
            return

        # Проверяем, включено ли авто-скрытие
        if not self.settings.get("auto_hide_controls", True):
            self.hide_timer.stop()
            return

        # Запускаем таймер, только если видео играет
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
        self.hide_timer.stop()

    def hide_controls(self):
        # Не прячем, если мы скраббим или если видео не играет
        if self.is_scrubbing or not self.is_playing:
            return

        # Проверяем, включено ли авто-скрытие
        if not self.settings.get("auto_hide_controls", True):
            return

        # Не прячем, если мышь находится над областью плеера
        pos = QCursor.pos()
        widget_under_mouse = QApplication.widgetAt(pos)
        if widget_under_mouse and (self.controls.isAncestorOf(widget_under_mouse) or
                                   self.title_bar.isAncestorOf(widget_under_mouse) or
                                   widget_under_mouse == self.controls or widget_under_mouse == self.title_bar):
            return

        # Не прячем, если мышь в нижней части окна
        local_pos = self.mapFromGlobal(pos)
        if local_pos.y() > self.height() - 60:
            return

        if not self.controls_visible:
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
    def set_track_vol(self, index: int, value: int):
        gain = value / 100.0
        display_percentage = value * 4
        # Set audio manager volume for the given index
        self.audio.set_track_vol(index, gain)
        # Update the UI label for that track
        self.controls.set_track_vol_label(index, f"{display_percentage}%")

        # Save volume if remember setting is enabled
        if self.settings.get("remember_volumes", False):
            self.settings["saved_volumes"][f"track_{index}"] = value
            save_settings(self.settings)

    def set_track_mute(self, index: int, muted: bool):
        if muted:
            self.audio.set_track_vol(index, 0.0)
        else:
            # Восстанавливаем громкость по текущему положению слайдера дорожки.
            try:
                _, slider, _ = self.controls._track_widgets[index]
                self.audio.set_track_vol(index, slider.value() / 100.0)
            except Exception:
                pass

    def apply_saved_volumes(self, saved_volumes):
        """Apply saved volumes to audio players and UI sliders"""
        for i in range(len(self.audio.audio_players)):
            track_key = f"track_{i}"
            if track_key in saved_volumes:
                volume = saved_volumes[track_key]
            
                # Apply to audio output
                gain = volume / 100.0
                self.audio.audio_outputs[i].setVolume(gain)
            
                # Update UI slider
                if i < len(self.controls._track_widgets):
                    _, slider, vol_label = self.controls._track_widgets[i]
                    slider.blockSignals(True)
                    slider.setValue(volume)
                    slider.blockSignals(False)
                
                    # Update label
                    display_percentage = volume * 4
                    vol_label.setText(f"{display_percentage}%")

    def update_vol_ui(self, num_audio_tracks):
        # create dynamic controls for N tracks
        orientation = self.settings.get("slider_orientation", "horizontal")
        self.controls.populate_track_controls(num_audio_tracks, orientation)
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
        self.recent_menu.clear()
        recent_files = self.settings.get("recent_files", [])
        if not recent_files:
            empty_action = self.recent_menu.addAction("(empty)")
            empty_action.setEnabled(False)
            return
        for path in recent_files:
            label = os.path.basename(path)
            action = self.recent_menu.addAction(label, partial(self.load_video_from_path, path))
            action.setToolTip(path)
        self.recent_menu.addSeparator()
        self.recent_menu.addAction("Clear Recent", self.clear_recent_files)

    def clear_recent_files(self):
        self.settings["recent_files"] = []
        save_settings(self.settings)
        self.rebuild_recent_menu()

    def add_recent_file(self, file_path):
        recent_files = self.settings.get("recent_files", [])
        # Убираем повтор, кладём в начало, ограничиваем длину списка
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
        # Отменяем предыдущий поток, если он был
        if self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.cancel()
            self.extraction_thread.wait()
            self.extraction_thread = None

        self.audio.cleanup_temp_files()
        self.current_video_path = file_path
        self._detected_resolution = None
        self.add_recent_file(file_path)
        # Видео загружается сразу и не зависит от наличия аудиодорожек.
        self.video.set_media(self.current_video_path)
        self.video.set_video_muted()
        self.controls.set_info_text("Detecting audio tracks...")

        # Создаём и запускаем поток
        self.extraction_thread = AudioExtractorThread(file_path, self.audio, self)
        self.extraction_thread.audio_tracks_detected.connect(self.update_vol_ui)
        self.extraction_thread.video_resolution_detected.connect(self.on_video_resolution_detected)
        self.extraction_thread.extraction_progress.connect(self.controls.set_info_text)
        self.extraction_thread.extraction_finished.connect(self.on_extraction_finished)
        self.extraction_thread.extraction_error.connect(self.on_extraction_error)
        self.extraction_thread.start()

    def on_video_resolution_detected(self, width, height):
        # Пришло из фонового потока вместе с детектом аудио — отдельный
        # синхронный ffprobe-вызов на GUI-потоке больше не нужен.
        self._detected_resolution = (width, height)
        
    def on_extraction_error(self, error_msg):
        # Ошибка аудио не должна блокировать воспроизведение видео.
        self.controls.set_info_text(f"Video loaded. Audio unavailable: {error_msg}")
        self.extraction_thread = None
        
    def on_extraction_finished(self, temp_files):
        # Этот метод вызывается, когда извлечение завершено
        self.controls.set_info_text(f"Loaded {len(temp_files)} audio track(s). Click Play.")

        # Видео уже настроено до запуска фонового извлечения.
        # Аудиоплееры подготовлены в AudioManager; повторно назначаем источники.
        if temp_files:
            self.audio.setup_audio_players()
            self.audio.set_audio_src()
        else:
            self.controls.set_info_text("Video loaded (no audio tracks). Click Play.")

        # Загружаем сохранённые громкости
        if self.settings.get("remember_volumes", False):
            saved_volumes = self.settings.get("saved_volumes", {})
            QTimer.singleShot(250, lambda: self.apply_saved_volumes(saved_volumes))

        # Изменяем размер окна
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

        if not self.isFullScreen():
            self.resize(new_width, new_height)
            self.center_window()

        # Обновляем длительность, если она уже известна
        if self.video.dur() > 0:
            self.update_dur(self.video.dur())

        # Освобождаем поток
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
        # Таймер скрытия запускается только после паузы в движении мыши
        self.reset_hide_timer()

    def pause(self):
        self.video.pause()
        self.audio.pause()
        self.timer.stop()
        self.hide_timer.stop()
        # Обязательно показываем контролы при паузе
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

    def update_label(self, ms):
        seconds = ms // 1000
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02d}:{seconds:02d}"

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

    def preview_seek_pos(self, pos):
        dur = self.video.dur()
        self.controls.set_timeline_label(f"{self.update_label(pos)} / {self.update_label(dur)}")

        # Живое обновление картинки видео при перетаскивании ползунка (как на YouTube).
        # Троттлим через таймер, чтобы не заваливать декодер seek-запросами при быстром
        # движении мыши — берём только самую последнюю позицию.
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

    def vid_pos_chg(self, pos):
        pass

    def vid_state_chg(self, playing: bool):
        self.is_playing = playing
        if not playing:
            self.show_controls()

    def keyPressEvent(self, event):
        key = event.key()
        native = event.nativeVirtualKey() if hasattr(event, "nativeVirtualKey") else 0
        # Physical A/D keys on Windows, independent of keyboard layout.
        if native in (0x41, 0x44) or key in (Qt.Key.Key_A, Qt.Key.Key_D):
            delta = -5000 if native == 0x41 or key == Qt.Key.Key_A else 5000
            self.seek_relative(delta)
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
        QTimer.singleShot(30, self.video.pause)

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
            # Восстанавливаем сохранённую геометрию, если она есть
            if self.normal_geometry:
                # Восстанавливаем позицию и размер
                self.setGeometry(self.normal_geometry)
                self.normal_geometry = None
        else:
            # Сохраняем текущую геометрию перед переходом в полноэкранный режим
            self.normal_geometry = self.geometry()
            self.showFullScreen()
            self.maximize_button.setText("v")

    def get_resize_edge(self, pos):
        # Determines if the position is near an edge.
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()

        if self.isMaximized() or self.isFullScreen():
            return 0

        # Увеличиваем зону для захвата края
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
                # Starts the system resize handler
                self.windowHandle().startSystemResize(edge)
                return

            # Проверяем, что клик был по заголовку
            title_bar_rect = self.title_bar.geometry()
            if title_bar_rect.contains(event.pos()):
                self.dragPos = event.globalPosition().toPoint()
            else:
                self.dragPos = QPoint()

    def mouseMoveEvent(self, event):
        # Проверка на ресайз и перетаскивание
        if event.buttons() == Qt.MouseButton.LeftButton and self.dragPos != QPoint():
            new_pos = self.pos() + event.globalPosition().toPoint() - self.dragPos

            # Полноэкранный режим не включается автоматически при касании верхнего края.
            if self.isFullScreen():
                # Потянуть верхнюю панель вниз: восстановить прежний размер.
                if event.globalPosition().toPoint().y() > 20:
                    self.toggle_maximize()
                    self.dragPos = event.globalPosition().toPoint()
                return

            # При перетаскивании верхней панели к верхнему краю включаем настоящий fullscreen.
            if new_pos.y() <= 0:
                self.toggle_maximize()
                self.dragPos = QPoint()
                return
            # Стандартное перетаскивание
            self.move(new_pos)
            self.dragPos = event.globalPosition().toPoint()
            return

        # Сброс таймера при движении мыши
        self.reset_hide_timer()

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
        save_theme(theme)

    def set_slider_orientation(self, orientation):
        """Change slider orientation between horizontal and vertical"""
        self.settings["slider_orientation"] = orientation
        save_settings(self.settings)
    
        self.horizontal_slider_action.setChecked(orientation == "horizontal")
        self.horizontal_slider_action.setText(
            "● Horizontal Sliders" if orientation == "horizontal" else "○ Horizontal Sliders"
        )
    
        self.vertical_slider_action.setChecked(orientation == "vertical")
        self.vertical_slider_action.setText(
            "● Vertical Sliders" if orientation == "vertical" else "○ Vertical Sliders"
        )
    
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
        self.remember_volumes_action.setText(
            "✓ Remember Volume Levels" if new_value else "x Remember Volume Levels"
        )

    def set_hide_delay(self, milliseconds):
        self.settings["hide_delay"] = milliseconds
        save_settings(self.settings)
        self.hide_timer.setInterval(milliseconds)
        for value, action in self.hide_delay_actions.items():
            action.setChecked(value == milliseconds)

    def toggle_controls_visibility(self):
        if self.controls_visible or self.title_visible:
            self.hide_timer.stop()
            self.animation.stop(); self.animation.setStartValue(self.controls.maximumHeight()); self.animation.setEndValue(0); self.animation.start()
            self.title_animation.stop(); self.title_animation.setStartValue(self.title_bar.maximumHeight()); self.title_animation.setEndValue(0); self.title_animation.start()
            self.controls_visible = False; self.title_visible = False
        else:
            self.show_controls()

    def toggle_auto_hide(self):
        """Toggle auto-hide controls setting"""
        current = self.settings.get("auto_hide_controls", True)
        new_value = not current
        self.settings["auto_hide_controls"] = new_value
        save_settings(self.settings)
        self.auto_hide_action.setChecked(new_value)
        self.auto_hide_action.setText(
            "✓ Auto-hide Controls" if new_value else "x Auto-hide Controls"
        )
        if not new_value:
            self.show_controls()

    def toggle_fullscreen_on_start(self):
        """Toggle fullscreen on start setting"""
        current = self.settings.get("fullscreen_on_start", False)
        new_value = not current
        self.settings["fullscreen_on_start"] = new_value
        save_settings(self.settings)
        self.fullscreen_start_action.setChecked(new_value)
        self.fullscreen_start_action.setText(
            "✓ Fullscreen on Start" if new_value else "x Fullscreen on Start"
        )

    def export_video(self):
        """Export video with mixed audio tracks using ffmpeg (runs in background thread)"""
        from PyQt6.QtWidgets import QMessageBox

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

            # Add all audio track files as inputs
            for temp_file in self.audio.temp_files:
                cmd.extend(["-i", temp_file])

            # Build filter_complex for audio mixing with volume adjustments
            filter_parts = []
            for i in range(num_tracks):
                # Get the current volume from the slider (0-100, where 25 = 100%)
                try:
                    _, slider, _ = self.controls._track_widgets[i]
                    slider_value = slider.value()
                    # Convert slider value to volume multiplier (slider 25 = 1.0x, 100 = 4.0x)
                    volume = slider_value / 25.0
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

            # Запускаем ffmpeg в фоновом потоке, чтобы окно не зависало на время экспорта.
            self.export_thread = ExportThread(cmd, output_path, self)
            self.export_thread.export_finished.connect(partial(self.on_export_finished, was_playing))
            self.export_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{str(e)}")
            self.controls.set_info_text(f"Export error: {str(e)}")
            print("Export exception:", e)
            if was_playing:
                self.play()

    def on_export_finished(self, was_playing, success, message):
        from PyQt6.QtWidgets import QMessageBox
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
        self.controls.populate_track_controls(num_tracks, orientation)
    
        for i, volume in enumerate(current_volumes):
            if i < len(self.controls._track_widgets):
                _, slider, _ = self.controls._track_widgets[i]
                slider.setValue(volume)
        
        self.refresh_controls_target_height()

    # ----- Cleanup ----- #
    def closeEvent(self, event):
        self.timer.stop()
        self.hide_timer.stop()

        if self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.cancel()
            self.extraction_thread.wait()

        if self.export_thread and self.export_thread.isRunning():
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
        app.setStyleSheet(DARK_THEME)
    else:
        app.setStyleSheet(LIGHT_THEME)

    player = MainWindow()

    if len(sys.argv) > 1:
        path = sys.argv[1]
        player.load_video_from_path(path)

    player.show()
    player.activateWindow()
    player.raise_()
    player.setFocus()
    sys.exit(app.exec())
