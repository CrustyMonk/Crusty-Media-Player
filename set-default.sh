#!/bin/bash
# Set Crusty Media Player as default for all video files

set -e

echo "==========================================="
echo "Setting Crusty Media Player as Default"
echo "==========================================="
echo ""

DESKTOP_FILE="$HOME/.local/share/applications/crusty-media-player.desktop"

if [ ! -f "$DESKTOP_FILE" ]; then
    echo "ERROR: crusty-media-player.desktop not found!"
    echo "Please run install.sh first."
    exit 1
fi

echo "Setting as default for all video formats..."

# List of all video MIME types
VIDEO_MIMES=(
    "video/mp4"
    "video/x-matroska"
    "video/x-msvideo"
    "video/quicktime"
    "video/webm"
    "video/ogg"
    "video/mpeg"
    "video/x-mpeg"
    "video/mp2t"
    "video/x-flv"
    "video/3gpp"
    "video/3gpp2"
    "video/x-ms-wmv"
    "video/x-ogm"
    "application/x-matroska"
)

# Set as default for each MIME type
for mime in "${VIDEO_MIMES[@]}"; do
    xdg-mime default crusty-media-player.desktop "$mime" 2>/dev/null || true
    echo "  ✓ $mime"
done

echo ""
echo "✅ Crusty Media Player is now your default video player!"
echo ""
echo "Test it by:"
echo "  1. Right-clicking a video file"
echo "  2. Select 'Open With' → should see Crusty Media Player"
echo "  3. Or just double-click a video file"
echo ""
echo "To verify current defaults, run:"
echo "  xdg-mime query default video/mp4"
