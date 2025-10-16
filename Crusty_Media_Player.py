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
        self.setWindowTitle("Crusty Media Player 0.1.1")
        self.setGeometry(900, 200, 900, 600)

        # Video Widget
        self.video_widget = QVideoWidget()
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)

        # GUI Buttons
        self.open_button = QPushButton("Open Media")
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")

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
        controls_layout.addWidget(self.pause_button)
        controls_layout.addWidget(self.stop_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.video_widget, stretch=1)
        main_layout.addWidget(self.timeline_label)
        main_layout.addWidget(self.timeline_slider)
        main_layout.addWidget(self.info_label)
        main_layout.addLayout(controls_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Connections
        self.open_button.clicked.connect(self.load_video)
        self.play_button.clicked.connect(self.play)
        self.pause_button.clicked.connect(self.pause)
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
    player.show()
    sys.exit(app.exec())