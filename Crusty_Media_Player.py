import sys
import os
import tempfile
import ffmpeg
import subprocess
import json

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QPoint, QPropertyAnimation, QEvent, QEasingCurve
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSlider, QWidget, QPushButton, QVBoxLayout, 
    QHBoxLayout, QFileDialog, QLabel
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QShortcut, QCursor

# The width in pixels where the window detects a resize drag on the border.
BORDER_SIZE = 8

# Force ffmpeg-python to use bundled ffmpeg.exe 
# Note: This path logic assumes an environment where ffmpeg.exe is adjacent to the script.
ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe') 
if os.path.exists(ffmpeg_path): 
    # Use the absolute path logic more robustly
    os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"] 

class MediaPlayer(QMainWindow): 
    def __init__(self): 
        super().__init__() 
        
        # --- Window Setup ---
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint) 
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) 
        self.setGeometry(200, 100, 1600, 900) 
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # --- Media Players & State ---
        self.audio_player1 = QMediaPlayer() 
        self.audio_output1 = QAudioOutput() 
        self.audio_player1.setAudioOutput(self.audio_output1) 
        self.audio_output1.setVolume(0.25) 

        self.audio_player2 = QMediaPlayer() 
        self.audio_output2 = QAudioOutput() 
        self.audio_player2.setAudioOutput(self.audio_output2) 
        self.audio_output2.setVolume(0.25) 
        
        self.video_widget = QVideoWidget() 
        self.media_player = QMediaPlayer() 
        self.media_player.setVideoOutput(self.video_widget) 
        
        # Initial drag position for window movement 
        self.dragPos = QPoint()
        self.is_playing = False
        self.temp_files = [] # For cleanup
        self.is_scrubbing = False # Flag to prevent player seeking during slider drag

        # --- GUI Elements ---
        self.open_button = QPushButton("Open Media") 
        self.play_button = QPushButton("Play") 
        self.stop_button = QPushButton("Stop") 

        # Custom title bar (kept visible always)
        self.title_bar = QWidget() 
        self.title_bar.setFixedHeight(40) 
        self.title_label = QLabel("Crusty Media Player 0.2.2")
        self.title_label.setStyleSheet("font-weight: bold; color: white; padding-left: 10px;") 
        
        self.close_button = QPushButton("✕") 
        self.close_button.setFixedSize(30, 30) 
        self.close_button.setStyleSheet("background: none; color: #aaa; border: none;") 
        self.close_button.clicked.connect(self.close) 

        self.minimize_button = QPushButton("—")
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.setStyleSheet("background: none; color: #aaa; border: none;")
        self.minimize_button.clicked.connect(self.showMinimized)

        self.maximize_button = QPushButton("^")
        self.maximize_button.setFixedSize(30, 30)
        self.maximize_button.setStyleSheet("background: none; color: #aaa; border: none;")
        self.maximize_button.clicked.connect(self.toggle_maximize)

        # Timeline slider 
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal) 
        self.timeline_slider.setRange(0, 0) 
        self.timeline_slider.sliderPressed.connect(self.start_scrub) 
        self.timeline_slider.sliderReleased.connect(self.end_scrub) 
        
        # Switched from seeking (heavy operation) to previewing (light operation) on move
        self.timeline_slider.sliderMoved.connect(self.preview_seek_position) 
        
        # Timeline label 
        self.timeline_label = QLabel("00:00 / 00:00") 
        
        # Info Label 
        self.info_label = QLabel("No File Loaded") 
        
        # Track 1 Volume
        self.track1_label = QLabel("Track 1 Volume:")
        self.track1_slider = QSlider(Qt.Orientation.Horizontal)
        self.track1_slider.setRange(0, 100) 
        self.track1_slider.setValue(25) # Default 25% value = 100% audio gain
        self.track1_value_label = QLabel("100%") 
        self.track1_slider.valueChanged.connect(self.set_track1_volume)

        # Track 2 Volume
        self.track2_label = QLabel("Track 2 Volume:")
        self.track2_slider = QSlider(Qt.Orientation.Horizontal)
        self.track2_slider.setRange(0, 100) 
        self.track2_slider.setValue(25) # Default 25% value = 100% audio gain
        self.track2_value_label = QLabel("100%") 
        self.track2_slider.valueChanged.connect(self.set_track2_volume)

        # --- Layouts ---
        
        # 1. Control Panel Widgets
        controls_layout = QHBoxLayout() 
        controls_layout.addWidget(self.open_button) 
        controls_layout.addWidget(self.play_button) 
        controls_layout.addWidget(self.stop_button)

        volume_controls = QHBoxLayout()
        volume_controls.addWidget(self.track1_label)
        volume_controls.addWidget(self.track1_slider)
        volume_controls.addWidget(self.track1_value_label) 
        volume_controls.addWidget(self.track2_label)
        volume_controls.addWidget(self.track2_slider)
        volume_controls.addWidget(self.track2_value_label) 

        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(self.timeline_label)
        timeline_layout.addWidget(self.timeline_slider)

        # 2. Control Panel Container
        self.control_panel_container = QWidget()
        self.control_panel_container.setStyleSheet("QWidget {background-color: #121212; border-top: 1px solid #2A2A2A;}")
        
        control_panel_vbox = QVBoxLayout(self.control_panel_container)
        control_panel_vbox.setContentsMargins(10, 5, 10, 10)
        control_panel_vbox.setSpacing(5)
        
        control_panel_vbox.addLayout(timeline_layout)
        control_panel_vbox.addWidget(self.info_label)
        control_panel_vbox.addLayout(volume_controls)
        control_panel_vbox.addLayout(controls_layout)

        # 3. Main Layout
        title_layout = QHBoxLayout(self.title_bar) 
        title_layout.addWidget(self.title_label) 
        title_layout.addStretch() 
        title_layout.addWidget(self.minimize_button)
        title_layout.addWidget(self.maximize_button)
        title_layout.addWidget(self.close_button)
        title_layout.setContentsMargins(5, 0, 5, 0) 
        
        main_layout = QVBoxLayout() 
        main_layout.addWidget(self.title_bar) 
        main_layout.addWidget(self.video_widget, stretch=1) 
        main_layout.addWidget(self.control_panel_container)
        
        container = QWidget() 
        container.setLayout(main_layout) 
        self.setCentralWidget(container)
        
        # --- Animation and Timer Setup ---
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        
        # Calculate initial height of controls container after layout is built
        QApplication.processEvents() 
        self.target_height = self.control_panel_container.height()
        self.control_panel_container.setMaximumHeight(self.target_height)
        self.controls_visible = True
        
        # Animation setup
        self.animation = QPropertyAnimation(self.control_panel_container, b"maximumHeight")
        self.animation.setDuration(350) # Animation duration in ms
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Mouse Idle Timer (3.0 seconds of inactivity)
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(3000) 
        self.hide_timer.timeout.connect(self.hide_controls)
        
        # ------------------ Mouse Tracking and Event Filtering ------------------ #
        # Enable mouse tracking on all interactive widgets so we get MouseMove events everywhere
        self.setMouseTracking(True)                       # Main window
        self.video_widget.setMouseTracking(True)          # Video area
        self.control_panel_container.setMouseTracking(True)  # Controls panel
        self.title_bar.setMouseTracking(True)            # Custom title bar

        # Install event filter on all these widgets so eventFilter() is triggered
        QApplication.instance().installEventFilter(self)
        # ------------------------------------------------------------------------ #

        # --- Connections ---
        space_shortcut = QShortcut(Qt.Key.Key_Space, self)
        space_shortcut.activated.connect(self.toggle_play_pause)
        
        self.open_button.clicked.connect(self.load_video) 
        self.play_button.clicked.connect(self.toggle_play_pause) 
        self.stop_button.clicked.connect(self.stop) 
        
        # Timer for timeline slider 
        self.timer = QTimer() 
        self.timer.setInterval(50) 
        self.timer.timeout.connect(self.update_timeline) 
        
        self.was_playing = False # Track if audio and video was playing before scrubbing


    # --- Control Visibility Logic ---

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseMove:
            self.reset_hide_timer()  # Reset hide timer for ANY mouse move
            return False  # Let event continue
        return super().eventFilter(obj, event)

    def reset_hide_timer(self):
        # Always show controls when mouse moves
        self.show_controls()

        # Check if mouse is over a slider (timeline or volume sliders)
        widget_under_mouse = QApplication.widgetAt(QCursor.pos())
        if isinstance(widget_under_mouse, QSlider) or self.is_scrubbing:
            self.hide_timer.stop()  # Don’t hide while dragging sliders
            return

        # Only hide automatically if video is playing
        if self.is_playing:
            self.hide_timer.start()
        else:
            self.hide_timer.stop() 

    def show_controls(self):       
        # Animates the controls container to be fully visible and restores cursor.

        # Only start the animation if the controls are actually hidden
        if not self.controls_visible:
            self.animation.stop()
            self.animation.setStartValue(self.control_panel_container.maximumHeight())
            self.animation.setEndValue(self.target_height)
            self.animation.start()
            self.controls_visible = True
        
        # Always restore cursor to Arrow on show/reset.
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def hide_controls(self):
        # Animates the controls container to hide and hides cursor.
        if not self.controls_visible or not self.is_playing or self.is_scrubbing:
            return

        self.animation.stop()
        self.animation.setStartValue(self.target_height)
        self.animation.setEndValue(0)
        self.animation.start()
        self.controls_visible = False
        self.hide_timer.stop()

        self.setCursor(Qt.CursorShape.BlankCursor)
        
    # --- Volume Gain Methods ---
    def set_track1_volume(self, value):
        gain = value / 100.0
        display_percentage = value * 4
        self.audio_output1.setVolume(gain)
        self.track1_value_label.setText(f"{display_percentage}%")

    def set_track2_volume(self, value):
        gain = value / 100.0
        display_percentage = value * 4
        self.audio_output2.setVolume(gain)
        self.track2_value_label.setText(f"{display_percentage}%")

    # --- Volume UI adjustment based on number of audio tracks ---
    def update_volume_ui(self, num_audio_tracks):
        # Adjusts the visibility and labels of volume controls
        # depending on the number of detected audio tracks.
        if num_audio_tracks == 1:
            # Hide Track 2 controls
            self.track2_label.hide()
            self.track2_slider.hide()
            self.track2_value_label.hide()
        
            # Change Track 1 label to "Volume"
            self.track1_label.setText("Volume:")
        else:
            # Show Track 2 controls
            self.track2_label.show()
            self.track2_slider.show()
            self.track2_value_label.show()
        
            # Restore Track 1 label
            self.track1_label.setText("Track 1 Volume:")
        
    # --- Media Loading and Control ---
    def load_video(self): 
        file_path, _ = QFileDialog.getOpenFileName( 
            self, "Select Video File", "", "Video Files (*.mp4 *.mkv *.avi *.mov)" 
        ) 
        if not file_path: 
            return 
        
        self.info_label.setText(f"Loading audio tracks from:\n{os.path.basename(file_path)}") 
        
        # Cleanup old temp files
        for f in self.temp_files:
            try: os.unlink(f) 
            except: pass
        self.temp_files = [] 

        # Detect number of audio streams using ffprobe
        try:
            # Prepare command
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "json",
                file_path
            ]

            # Run ffprobe with hidden window
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Parse output
            probe_data = json.loads(result.stdout)
            audio_streams = probe_data.get("streams", [])
            num_audio_tracks = len(audio_streams)

        except Exception as e:
            self.info_label.setText("Error reading media file.")
            return
        
        self.update_volume_ui(num_audio_tracks)

        if num_audio_tracks == 0:
            self.info_label.setText("No audio tracks found in the selected file.") 
            return
        
        # Extract up to 2 audio tracks as WAV 
        for i in range(min(num_audio_tracks, 2)): 
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav") 
            temp_file.close() 
            try: 
                # FFmpeg is used to extract and boost the audio
                cmd = ( 
                    ffmpeg 
                    .input(file_path) 
                    .output(temp_file.name, map=f'0:a:{i}', af='volume=4.0', ac=2, ar='44100') 
                    .overwrite_output() 
                    .compile() 
                    ) 
                
                subprocess.run( 
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL, 
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0 
                    ) 

                self.temp_files.append(temp_file.name) 
            except ffmpeg.Error as e: 
                break 
            
        if len(self.temp_files) < 1: 
            self.info_label.setText("No audio tracks found in the selected file.") 
            return 
        
        # Set video source 
        self.media_player.setSource(QUrl.fromLocalFile(file_path)) 
        self.media_player.setAudioOutput(None) # Mute the video's default audio output
        
        # Assign extracted audio tracks to QMediaPlayer 
        self.audio_player1.setSource(QUrl.fromLocalFile(self.temp_files[0])) 
        if len(self.temp_files) > 1: 
            self.audio_player2.setSource(QUrl.fromLocalFile(self.temp_files[1])) 
            
        self.info_label.setText(f"Loaded {len(self.temp_files)} audio track(s). Click Play.") 
        
        # Update timeline 
        self.media_player.durationChanged.connect(self.update_duration)

        if self.media_player.duration() > 0:
            self.update_duration(self.media_player.duration())

        
    def toggle_play_pause(self):
        if self.media_player.source().isEmpty():
            self.load_video()
            return
            
        if not self.is_playing:
            self.play()
            self.play_button.setText("Pause")
            self.is_playing = True
        else:
            self.pause()
            self.play_button.setText("Play")
            self.is_playing = False
            
    def play(self): 
        self.media_player.play() 
        self.audio_player1.play() 
        if len(self.temp_files) > 1: 
            self.audio_player2.play() 
        
        self.timer.start() 
        self.hide_timer.start() # Start hide timer
            
    def pause(self): 
        self.media_player.pause() 
        self.audio_player1.pause() 
        if len(self.temp_files) > 1: 
            self.audio_player2.pause() 
            
        self.timer.stop() 
        self.hide_timer.stop() # Stop hide timer
        self.show_controls() # Force show controls

    def stop(self): 
        self.media_player.stop() 
        self.audio_player1.stop() 
        if len(self.temp_files) > 1: 
            self.audio_player2.stop() 
            
        self.timer.stop()
        self.hide_timer.stop()
        self.is_playing = False
        self.timeline_slider.setValue(0)
        self.timeline_label.setText("00:00 / 00:00")
        self.show_controls() # Force show controls
            
    def update_duration(self, duration): 
        self.timeline_slider.setRange(0, duration)
        self.timeline_label.setText(f"00:00 / {self.update_label(duration)}")
        
    def update_timeline(self): 
        # Do not update position while scrubbing to prevent conflicts
        if self.is_scrubbing: 
            return

        position = self.media_player.position() 
        duration = self.media_player.duration() 
        
        self.timeline_slider.blockSignals(True) 
        self.timeline_slider.setValue(position) 
        self.timeline_slider.blockSignals(False) 

        self.timeline_label.setText(f"{self.update_label(position)} / {self.update_label(duration)}")
        
    def update_label(self, ms): 
        seconds = ms // 1000 
        minutes = seconds // 60 
        seconds %= 60 
        return f"{minutes:02d}:{seconds:02d}" 
    
    #----------------------------Scrubbing Logic (Unchanged)----------------------------# 
    
    def preview_seek_position(self, position):
        # Updates the timeline label during scrubbing without seeking the media players (prevents freeze).
        duration = self.media_player.duration()
        self.timeline_label.setText(f"{self.update_label(position)} / {self.update_label(duration)}")

    def start_scrub(self): 
        self.was_playing = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState 
        self.is_scrubbing = True # Set flag
        self.media_player.pause() 
        self.audio_player1.pause() 
        if len(self.temp_files) > 1: 
            self.audio_player2.pause() 
        self.timer.stop() 
        self.hide_timer.stop() # Pause hiding during scrub
        
    def end_scrub(self): 
        self.is_scrubbing = False # Clear flag
        pos = self.timeline_slider.value() 
        
        # Actual seek operation (only done once on release)
        self.media_player.setPosition(pos) 
        self.audio_player1.setPosition(pos) 
        if len(self.temp_files) > 1: 
            self.audio_player2.setPosition(pos) 

        if self.was_playing: 
            self.media_player.play() 
            self.audio_player1.play() 
            if len(self.temp_files) > 1: 
                self.audio_player2.play() 
            self.timer.start() 
            self.hide_timer.start() # Resume hiding
        else:
            self.show_controls() # Keep controls visible if not playing
            
    #-----------------------------------------------------------------------# 
    

    #---------------Making Window Draggable & Resizable---------------------# 

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.maximize_button.setText("^")
        else:
            self.showMaximized()
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
        # the mouse moves, preventing stuck cursors, unless a boundary is immediately detected.
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
        
    #-----------------------------------------------------------------------# 
    
    def closeEvent(self, event): 
        # Clean up temporary files on close. 
        self.stop() 
        for f in self.temp_files: 
            try: 
                os.unlink(f) 
            except Exception as e: 
                pass 
        event.accept() 
        
if __name__ == "__main__": 
    app = QApplication(sys.argv) 
    player = MediaPlayer() 
    app.setStyleSheet("""
    QMainWindow {
        background-color: #121212;
        border: 2px solid #00ADB5; /* Added a subtle border for frameless window */
        border-radius: 8px;
    }

    QWidget {
        background-color: #121212;
        color: #EAEAEA;
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
    }

    QLabel {
        color: #EAEAEA;
    }

    QPushButton {
        background-color: #1F1F1F;
        border: 1px solid #2E2E2E;
        border-radius: 8px;
        padding: 6px 12px;
        color: #EAEAEA;
        font-weight: 500;
    }

    QPushButton:hover {
        background-color: #2E2E2E;
        border: 1px solid #3E3E3E;
    }

    QPushButton:pressed {
        background-color: #00ADB5;
        color: #000;
    }
    
    /* Title Bar Buttons Style */
    #QWidget QPushButton {
        background: none;
        border: none;
        padding: 0;
        margin: 0;
    }
    
    /* Close Button Styling for better UX */
    QPushButton:hover[text="✕"] {
        background-color: #C42B1C;
        color: white;
    }

    QSlider::groove:horizontal {
        background: #333;
        height: 6px;
        border-radius: 3px;
    }

    QSlider::handle:horizontal {
        background: #00ADB5;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }

    QSlider::sub-page:horizontal {
        background: #00ADB5;
        border-radius: 3px;
    }

    QSlider::add-page:horizontal {
        background: #2A2A2A;
        border-radius: 3px;
    }
""")
    player.show() 
    sys.exit(app.exec())
