import sys 
import os 
import tempfile 
import ffmpeg 
import subprocess 
from PyQt6.QtCore import Qt, QUrl, QTimer 
from PyQt6.QtWidgets import (QApplication, QMainWindow, QSlider, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QLabel)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget 

# Force ffmpeg-python to use bundled ffmpeg.exe 
ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe') 
if os.path.exists(ffmpeg_path): 
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ["PATH"] 

class MediaPlayer(QMainWindow): 
    def __init__(self): 
        super().__init__() 
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint) 
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) 
        self.setWindowTitle("Crusty Media Player 0.2.0") 
        self.setGeometry(200, 100, 1600, 900) 

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # Store audio players and sliders for volume control
        self.audio_players = []
        self.audio_outputs = []
        self.audio_sliders = []

        # Video Widget 
        self.video_widget = QVideoWidget() 
        self.media_player = QMediaPlayer() 
        self.media_player.setVideoOutput(self.video_widget) 
        
        # GUI Buttons
        self.open_button = QPushButton("Open Media") 
        self.play_button = QPushButton("Play") 
        #self.pause_button = QPushButton("Pause") 
        self.stop_button = QPushButton("Stop") 

        # Track play/pause state
        self.is_playing = False
        
        # Custom title bar 
        self.title_bar = QWidget() 
        self.title_bar.setFixedHeight(40) 
        self.title_label = QLabel("Crusty Media Player 0.2.0") 
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
        self.timeline_slider.sliderMoved.connect(self.seek_position) 
        
        # Timeline label 
        self.timeline_label = QLabel("00:00 / 00:00") 
        
        # Info Label 
        self.info_label = QLabel("No File Loaded") 
        
        # Layouts 
        controls_layout = QHBoxLayout() 
        controls_layout.addWidget(self.open_button) 
        controls_layout.addWidget(self.play_button) 
        #controls_layout.addWidget(self.pause_button) 
        controls_layout.addWidget(self.stop_button)

        volume_controls = QHBoxLayout()
        self.track1_label = QLabel("Track 1 Volume:")
        self.track1_slider = QSlider(Qt.Orientation.Horizontal)
        self.track1_slider.setRange(0, 100)
        self.track1_slider.setValue(100)
        self.track1_slider.valueChanged.connect(lambda v: self.audio_output1.setVolume(v / 100))

        self.track2_label = QLabel("Track 2 Volume:")
        self.track2_slider = QSlider(Qt.Orientation.Horizontal)
        self.track2_slider.setRange(0, 100)
        self.track2_slider.setValue(100)
        self.track2_slider.valueChanged.connect(lambda v: self.audio_output2.setVolume(v / 100))

        volume_controls.addWidget(self.track1_label)
        volume_controls.addWidget(self.track1_slider)
        volume_controls.addWidget(self.track2_label)
        volume_controls.addWidget(self.track2_slider)
        
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
        main_layout.addWidget(self.timeline_label) 
        main_layout.addWidget(self.timeline_slider) 
        main_layout.addWidget(self.info_label)
        main_layout.addLayout(volume_controls)
        main_layout.addLayout(controls_layout)
        
        container = QWidget() 
        container.setLayout(main_layout) 
        self.setCentralWidget(container) 
        
        # Connections 
        self.open_button.clicked.connect(self.load_video) 
        self.play_button.clicked.connect(self.toggle_play_pause) 
        #self.pause_button.clicked.connect(self.pause) 
        self.stop_button.clicked.connect(self.stop) 
        
        # Dual Audio Players 
        self.audio_player1 = QMediaPlayer() 
        self.audio_output1 = QAudioOutput() 
        self.audio_player1.setAudioOutput(self.audio_output1) 

        self.audio_player2 = QMediaPlayer() 
        self.audio_output2 = QAudioOutput() 
        self.audio_player2.setAudioOutput(self.audio_output2) 
        
        # Temporary files 
        self.temp_files = [] 
        
        # Timer for timeline slider 
        self.timer = QTimer() 
        self.timer.setInterval(50) 
        self.timer.timeout.connect(self.update_timeline) 
        
        # Track is audio and video was playing before scrubbing 
        self.was_playing = False
        
    def load_video(self): 
        """Load video and extract up to 2 audio tracks using ffmpeg.""" 
        file_path, _ = QFileDialog.getOpenFileName( 
            self, "Select Video File", "", "Video Files (*.mp4 *.mkv *.avi *.mov)" 
        ) 
        if not file_path: 
            return 
        
        self.info_label.setText(f"Loading audio tracks from:\n{file_path}") 
        self.temp_files = [] 
        
        # Extract up to 2 audio tracks as WAV 
        for i in range(2): 
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav") 
            temp_file.close() 
            try: 
                cmd = ( 
                    ffmpeg 
                    .input(file_path) 
                    .output(temp_file.name, map=f'0:a:{i}', ac=2, ar='44100') 
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
                print(f"Track {i+1} not available: {e}") 
                break 
            
        if len(self.temp_files) < 1: 
            self.info_label.setText("No audio tracks found in the selected file.") 
            return 
        
        # Assign extracted audio tracks to QMediaPlayer 
        self.audio_player1.setSource(QUrl.fromLocalFile(self.temp_files[0])) 
        if len(self.temp_files) > 1: 
            self.audio_player2.setSource(QUrl.fromLocalFile(self.temp_files[1])) 
            
        # Set video source 
        self.media_player.setSource(QUrl.fromLocalFile(file_path)) 
        self.info_label.setText(f"Loaded {len(self.temp_files)} audio track(s).") 
        
        # Update timeline 
        self.media_player.durationChanged.connect(self.update_duration)
        
    def toggle_play_pause(self):
        # Toggle between playing and pausing the media
        if not self.is_playing:
            self.play()
            self.play_button.setText("Pause")
            self.is_playing = True
        else:
            self.pause()
            self.play_button.setText("Play")
            self.is_playing = False

    def keyPressEvent(self, event):
        # Spacebar toggles play/pause
        if event.key() == Qt.Key.Key_Space:
            self.toggle_play_pause()
        else:
            super().keyPressEvent(event)
        
    def play(self): 
        # Play video and both audio tracks 
        self.media_player.play() 
        self.audio_player1.play() 
        if len(self.temp_files) > 1: 
            self.audio_player2.play() 
            self.timer.start() 
            
    def pause(self): 
        # Pause video and both audio tracks. 
        self.media_player.pause() 
        self.audio_player1.pause() 
        if len(self.temp_files) > 1: 
            self.audio_player2.pause() 
            self.timer.stop() 

    def stop(self): 
        # Stop video and both audio tracks. 
        self.media_player.stop() 
        self.audio_player1.stop() 
        if len(self.temp_files) > 1: 
            self.audio_player2.stop() 
            self.timer.stop()
            
        self.is_playing = False
            
    def update_duration(self, duration): 
        # Update timeline slider range. 
        self.timeline_slider.setRange(0, duration) 
        
    def update_timeline(self): 
        # Update timeline slider position. 
        position = self.media_player.position() 
        duration = self.media_player.duration() 
        
        # Prevent slider signal loop 
        self.timeline_slider.blockSignals(True) 
        self.timeline_slider.setValue(self.media_player.position()) 
        self.timeline_slider.blockSignals(False) 
        
    def update_label(ms): 
        seconds = ms // 1000 
        minutes = seconds // 60 
        seconds %= 60 
        return f"{minutes:02d}:{seconds:02d}" 
    
        self.timeline_label.setText(f"{update_label(position)} / {update_label(duration)}") 
    
    #----------------------------Scrubbing Logic----------------------------# 
    def start_scrub(self): 
        # Pause audio and video while the user is scrubbing 
        self.was_playing = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState 
        self.media_player.pause() 
        self.audio_player1.pause() 
        if len(self.temp_files) > 1: 
            self.audio_player2.pause() 
            self.timer.stop() 
            
    def seek_position(self, position): 
        # Seek to position in video and both audio tracks. 
        self.media_player.setPosition(position) 
        self.audio_player1.setPosition(position) 
        if len(self.temp_files) > 1: 
            self.audio_player2.setPosition(position) 
            
    def end_scrub(self): 
        # Resume audio and video if they were playing before scrubbing 
        pos = self.timeline_slider.value() 
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

    #-----------------------------------------------------------------------#   
    

    #--------------------------Making Window Draggable----------------------# 

    def toggle_maximize(self):
        # Give the maximize/minimize button functionality
        if self.isMaximized():
            self.showNormal()
        else:
         self.showMaximized()

    def mousePressEvent(self, event): 
        if event.button() == Qt.MouseButton.LeftButton: 
            self.dragPos = event.globalPosition().toPoint() 
            
    def mouseMoveEvent(self, event): 
        if event.buttons() == Qt.MouseButton.LeftButton: 
            self.move(self.pos() + event.globalPosition().toPoint() - self.dragPos) 
            self.dragPos = event.globalPosition().toPoint() 
    #-----------------------------------------------------------------------# 
    
    def closeEvent(self, event): 
        # Clean up temporary files on close. 
        self.stop() 
        for f in self.temp_files: 
            try: 
                os.unlink(f) 
            except: 
                pass 
        event.accept() 
        

if __name__ == "__main__": 
    app = QApplication([]) 
    player = MediaPlayer() 
    app.setStyleSheet("""
    QMainWindow {
        background-color: #121212;
        border: none;
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
        transition: all 0.2s ease-in-out;
    }

    QPushButton:hover {
        background-color: #2E2E2E;
        border: 1px solid #3E3E3E;
    }

    QPushButton:pressed {
        background-color: #00ADB5;
        color: #000;
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