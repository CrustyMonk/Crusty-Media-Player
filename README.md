# Crusty Media Player
Crusty Media Player is an advanced video player for Linux with multi-track audio support, allowing you to control the volume of individual audio tracks independently. Perfect for videos with multiple audio tracks (commentary, language dubs, music tracks, etc.)

- **Crusty_Media_Player.py is the locally run version of the code wheras Crusty_Media_Player_Pkg.py is the version with file path specifications for the setup.exe (Windows)**

- **More information on features and troubleshooting is available inside the .zip in the latest releases**

# Windows Installation

**STEP 1: Extract the Files**
--------------------------
Extract the downloaded ZIP file to a folder:
  • Right-click the ZIP file
  • Select "Extract All..."
  • Choose a destination folder
  • Click "Extract"

You should have these files:
  • Crusty_Media_Player.exe
  • README.txt (this file)


**STEP 2: Install the Application**
--------------------------------

METHOD A: If you have a Setup/Installer:
  1. Right-click CrustyMediaPlayerSetup.exe
  2. Select "Run as administrator"
  3. Follow the setup prompts
  4. Click "Install" and wait for completion
  5. Click "Finish"


**STEP 3: Set as Default Video Player (Optional)**
-----------------------------------------------
To make Crusty your default video player:

  1. Press Windows Key
  2. Type "Default Apps" and open it
  3. Scroll down and click "Video player"
  4. Select "Crusty Media Player" from the list
  5. Close Settings

Now all video files will open in Crusty Media Player!


**STEP 4: Test the Installation**
------------------------------
  • Double-click any video file
  • Or right-click a video → Open with → Crusty Media Player
  • Or drag and drop a video onto Crusty's window

If it works, you're all set!

**================================================**

**ALTERNATIVE: Set Default via File Properties**

**================================================**

If the Default Apps method doesn't work:

  1. Right-click any video file (.mp4, .mkv, etc.)
  2. Select "Properties"
  3. Click "Change" next to "Opens with:"
  4. Select "Crusty Media Player"
  5. Check "Always use this app"
  6. Click OK

Repeat for each video format you want to open with Crusty.

# Linux Installation

**STEP 1: Extract the Files**
-------------------------
Extract the downloaded ZIP file to a folder:

  unzip CrustyMediaPlayer-Linux-v1.3.0.zip
  cd CrustyMediaPlayerLinux

You should have these files:
  • Crusty_Media_Player_Linux v1.3.0.py
  • icon/Crusty_Icon.ico
  • install.sh
  • set-default.sh
  • uninstall.sh
  • README.txt (this file)


**STEP 2: Run the Installer**
--------------------------
Open a terminal in the extracted folder and run:

  chmod +x install.sh
  ./install.sh

The installer will:
  1. Install system dependencies (requires sudo password)
  2. Install the application to ~/.local/share/crusty-media-player
  3. Install your custom icon
  4. Create a launcher command (crusty-media-player)
  5. Add desktop integration
  6. Ask if you want to set it as default video player


**STEP 3: Set as Default (Optional)**
----------------------------------
During installation, you'll be asked:
  "Set Crusty Media Player as default video player? [Y/n]"

Press Y to make Crusty your default video player.
Press N to skip (you can do this later with ./set-default.sh)


**STEP 4: Test the Installation**
------------------------------
From terminal:
  crusty-media-player /path/to/video.mp4

Or double-click any video file in your file manager!

If the command isn't found, add ~/.local/bin to your PATH:
  echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
  source ~/.bashrc

**================================================**

**SETTING AS DEFAULT VIDEO PLAYER**

**================================================**

**Method 1: During Installation**
------------------------------
The installer asks if you want to set Crusty as default.


**Method 2: After Installation (Command Line)**
--------------------------------------------
Run the set-default script:

  chmod +x set-default.sh
  ./set-default.sh


**Method 3: Manual**
---------------------------------------
  1. Right-click any video file
  2. Select "Properties" or "Open With"
  3. Click the "Open With" tab
  4. Find "Crusty Media Player" in the list
  5. Click "Set as default"
  6. Click OK/Apply

Done! Now all videos will open in Crusty Media Player.


**Method 4: Reset to System Default**
----------------------------------
To use your old video player again:

  1. Right-click a video → Properties → Open With
  2. Select your preferred player (VLC, MPV, etc.)
  3. Click "Set as default"

# Enjoy your videos with independent audio control!
