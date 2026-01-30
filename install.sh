#!/bin/bash
# Crusty Media Player - Complete Installation Script
# Handles: dependencies, app, icon, desktop integration, MIME associations

set -e

APP_NAME="crusty-media-player"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"

echo "================================================"
echo "Crusty Media Player - Installation"
echo "================================================"
echo ""

if [ "$EUID" -eq 0 ]; then
  echo "Please do not run this script as root."
  echo "It will ask for sudo password when needed."
  exit 1
fi

# Detect distro
if [ -f /etc/os-release ]; then
  . /etc/os-release
  DISTRO=$ID
else
  echo "Cannot detect Linux distribution"
  exit 1
fi

echo "Detected distribution: $DISTRO"
echo ""

echo "Step 1: Installing system dependencies..."
echo ""

case $DISTRO in
  arch|manjaro|endeavouros)
    sudo pacman -S --needed python python-pyqt6 python-mpv ffmpeg imagemagick
    ;;
  ubuntu|debian|pop|linuxmint)
    sudo apt update
    sudo apt install -y python3 python3-pyqt6 python3-mpv ffmpeg imagemagick
    ;;
  fedora|rhel|centos)
    sudo dnf install -y python3 python3-pyqt6 python3-mpv ffmpeg ImageMagick
    ;;
  opensuse*)
    sudo zypper install -y python3 python3-qt6 python3-mpv ffmpeg ImageMagick
    ;;
  *)
    echo "Unsupported distribution: $DISTRO"
    echo "Please manually install: python3, python3-pyqt6, python3-mpv, ffmpeg, imagemagick"
    exit 1
    ;;
esac

echo "  ✓ Dependencies installed"
echo ""

echo "Step 2: Installing application..."
echo ""

# Create install directories
mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR"
mkdir -p "$ICON_BASE/256x256/apps"
mkdir -p "$ICON_BASE/128x128/apps"
mkdir -p "$ICON_BASE/64x64/apps"
mkdir -p "$ICON_BASE/48x48/apps"
mkdir -p "$ICON_BASE/32x32/apps"
mkdir -p "$ICON_BASE/16x16/apps"

# Find the Python file
SRC_PY="$(find . -maxdepth 1 -name "*.py" -type f | head -n 1)"

if [ -z "$SRC_PY" ]; then
  echo "ERROR: No .py file found in current directory."
  exit 1
fi

echo "  Found: $SRC_PY"

# Check and add shebang if needed
FIRST_LINE=$(head -n 1 "$SRC_PY")
if [[ "$FIRST_LINE" == "#!/"* ]]; then
  echo "  ✓ Has shebang"
  cp -f "$SRC_PY" "$INSTALL_DIR/app.py"
else
  echo "  ⚠ Missing shebang - adding..."
  echo '#!/usr/bin/env python3' > "$INSTALL_DIR/app.py"
  cat "$SRC_PY" >> "$INSTALL_DIR/app.py"
fi

chmod +x "$INSTALL_DIR/app.py"
echo "  ✓ App installed to $INSTALL_DIR/app.py"
echo ""

echo "Step 3: Installing icon..."
echo ""

ICON_NAME="video-player"  # Default fallback

# Check for icon file
if [ -f "icon/Crusty_Icon.ico" ]; then
  echo "  Found: icon/Crusty_Icon.ico"
  
  # Check if ImageMagick is available
  if command -v convert >/dev/null 2>&1; then
    echo "  Converting ICO to PNG formats..."
    
    # Convert ICO to temporary PNGs
    convert "icon/Crusty_Icon.ico" /tmp/crusty-icon-%d.png 2>/dev/null
    
    # Find and install different sizes
    for img in /tmp/crusty-icon-*.png; do
      if [ -f "$img" ]; then
        SIZE=$(identify "$img" 2>/dev/null | grep -oP '\d+x\d+' | head -1)
        
        case $SIZE in
          256x256)
            cp "$img" "$ICON_BASE/256x256/apps/crusty-media-player.png"
            echo "    ✓ Installed 256x256 icon"
            ;;
          128x128)
            cp "$img" "$ICON_BASE/128x128/apps/crusty-media-player.png"
            echo "    ✓ Installed 128x128 icon"
            ;;
          64x64)
            cp "$img" "$ICON_BASE/64x64/apps/crusty-media-player.png"
            echo "    ✓ Installed 64x64 icon"
            ;;
          48x48)
            cp "$img" "$ICON_BASE/48x48/apps/crusty-media-player.png"
            echo "    ✓ Installed 48x48 icon"
            ;;
          32x32)
            cp "$img" "$ICON_BASE/32x32/apps/crusty-media-player.png"
            echo "    ✓ Installed 32x32 icon"
            ;;
          16x16)
            cp "$img" "$ICON_BASE/16x16/apps/crusty-media-player.png"
            echo "    ✓ Installed 16x16 icon"
            ;;
        esac
      fi
    done
    
    # Clean up temp files
    rm -f /tmp/crusty-icon-*.png
    
    # Update icon cache
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
      gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
      echo "  ✓ Icon cache updated"
    fi
    
    ICON_NAME="crusty-media-player"
    echo "  ✓ Custom icon installed"
  else
    echo "  ⚠ ImageMagick not available - using system icon"
    ICON_NAME="video-player"
  fi
else
  echo "  ⚠ No icon found at icon/Crusty_Icon.ico"
  echo "  Using system default icon"
  ICON_NAME="video-player"
fi

echo ""

echo "Step 4: Creating launcher..."
echo ""

cat > "$BIN_DIR/$APP_NAME" << 'EOF'
#!/bin/bash
exec "$HOME/.local/share/crusty-media-player/app.py" "$@"
EOF

chmod +x "$BIN_DIR/$APP_NAME"
echo "  ✓ Launcher created: $BIN_DIR/$APP_NAME"
echo ""

echo "Step 5: Creating desktop entry..."
echo ""

cat > "$DESKTOP_DIR/crusty-media-player.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Crusty Media Player
GenericName=Video Player
Comment=Advanced media player with multi-track audio support
TryExec=$INSTALL_DIR/app.py
Exec=$INSTALL_DIR/app.py %U
Icon=$ICON_NAME
Terminal=false
Categories=AudioVideo;Video;Player;Qt;
MimeType=video/mp4;video/x-matroska;video/x-msvideo;video/quicktime;video/webm;video/ogg;video/mpeg;video/x-mpeg;video/mp2t;video/x-flv;video/3gpp;video/3gpp2;video/x-ms-wmv;video/x-ogm;application/x-matroska;video/x-mpeg2;video/x-mpeg3;video/mkv;video/avi;video/dv;
Keywords=video;player;media;movie;audio;mkv;mp4;avi;
StartupNotify=true
EOF

chmod 644 "$DESKTOP_DIR/crusty-media-player.desktop"
echo "  ✓ Desktop file created"

# Validate desktop file
if command -v desktop-file-validate >/dev/null 2>&1; then
  if desktop-file-validate "$DESKTOP_DIR/crusty-media-player.desktop" 2>/dev/null; then
    echo "  ✓ Desktop file is valid"
  else
    echo "  ⚠ Desktop file has warnings (may still work)"
  fi
fi

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
  echo "  ✓ Desktop database updated"
fi

echo ""

echo "Step 6: Testing installation..."
echo ""

# Test the app can be found
if command -v crusty-media-player >/dev/null 2>&1; then
  echo "  ✓ Command available in PATH"
else
  echo "  ⚠ Command not in PATH"
  echo "    Add to your ~/.bashrc:"
  echo "    export PATH=\$HOME/.local/bin:\$PATH"
fi

# Test file is executable
if [ -x "$INSTALL_DIR/app.py" ]; then
  echo "  ✓ App is executable"
else
  echo "  ✗ App is NOT executable"
  chmod +x "$INSTALL_DIR/app.py"
fi

# Test shebang
if head -n 1 "$INSTALL_DIR/app.py" | grep -q "^#!/"; then
  echo "  ✓ Has shebang"
else
  echo "  ✗ Missing shebang!"
fi

echo ""
echo "================================================"
echo "Installation Complete!"
echo "================================================"
echo ""

# Ask about setting as default
read -p "Set Crusty Media Player as default video player? [Y/n] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Nn]$ ]]; then
  echo ""
  echo "Setting as default for all video formats..."
  
  # Comprehensive list of video MIME types
  VIDEO_MIMES=(
    "video/mp4"
    "video/x-matroska"
    "video/x-msvideo"
    "video/quicktime"
    "video/webm"
    "video/ogg"
    "video/mpeg"
    "video/x-mpeg"
    "video/x-mpeg2"
    "video/x-mpeg3"
    "video/mp2t"
    "video/x-flv"
    "video/flv"
    "video/3gp"
    "video/3gpp"
    "video/3gpp2"
    "video/x-ms-wmv"
    "video/x-ms-asf"
    "video/x-ms-wmx"
    "video/x-ogm"
    "video/mkv"
    "video/x-m4v"
    "video/mp4v-es"
    "video/divx"
    "video/vnd.divx"
    "video/msvideo"
    "video/avi"
    "video/dv"
    "application/x-matroska"
    "application/x-extension-mp4"
  )
  
  # Set using xdg-mime
  for mime in "${VIDEO_MIMES[@]}"; do
    xdg-mime default crusty-media-player.desktop "$mime" 2>/dev/null || true
  done
  
  # Also try gio if available
  if command -v gio >/dev/null 2>&1; then
    for mime in "${VIDEO_MIMES[@]}"; do
      gio mime "$mime" crusty-media-player.desktop 2>/dev/null || true
    done
  fi
  
  # Restart file managers
  pkill -9 nautilus nemo dolphin thunar pcmanfm caja 2>/dev/null || true
  
  echo "  ✓ MIME associations set"
  echo ""
  
  # Verify
  DEFAULT=$(xdg-mime query default video/mp4)
  if [[ "$DEFAULT" == "crusty-media-player.desktop" ]]; then
    echo "  ✅ Successfully set as default!"
  else
    echo "  ⚠ May need to log out/in for changes to take effect"
  fi
else
  echo ""
  echo "To set as default later, run:"
  echo "  ./set-default.sh"
fi

echo ""
echo "================================================"
echo "Next Steps"
echo "================================================"
echo ""
echo "1. Test from terminal:"
echo "   crusty-media-player /path/to/video.mp4"
echo ""
echo "2. If that works, double-clicking videos should too!"
echo "   (May need to log out and back in)"
echo ""
echo "3. Find in app menu: Search for 'Crusty'"
echo ""
echo "If ~/.local/bin is not in your PATH:"
echo "  echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc"
echo "  source ~/.bashrc"
echo ""
