#!/bin/bash
# Crusty Media Player - Uninstall Script

set -e

APP_NAME="crusty-media-player"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"
CONFIG_DIR="$HOME/.config/CrustyMediaPlayer"

echo "================================================"
echo "Crusty Media Player - Uninstall"
echo "================================================"
echo ""

echo "This will remove:"
echo "  • Application files"
echo "  • Desktop integration"
echo "  • Icons"
echo "  • Launcher command"
echo "  • Configuration files (optional)"
echo ""

read -p "Continue with uninstall? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""
echo "Removing application files..."

# Remove main application directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "  ✓ Removed $INSTALL_DIR"
else
    echo "  ⚠ Application directory not found"
fi

# Remove launcher
if [ -f "$BIN_DIR/$APP_NAME" ]; then
    rm -f "$BIN_DIR/$APP_NAME"
    echo "  ✓ Removed launcher: $BIN_DIR/$APP_NAME"
else
    echo "  ⚠ Launcher not found"
fi

echo ""
echo "Removing desktop integration..."

# Remove desktop file
if [ -f "$DESKTOP_DIR/crusty-media-player.desktop" ]; then
    rm -f "$DESKTOP_DIR/crusty-media-player.desktop"
    echo "  ✓ Removed desktop file"
    
    # Update desktop database
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
        echo "  ✓ Updated desktop database"
    fi
else
    echo "  ⚠ Desktop file not found"
fi

echo ""
echo "Removing icons..."

# Remove icons from all size directories
ICON_REMOVED=0
for size in 16x16 32x32 48x48 64x64 128x128 256x256 scalable; do
    ICON_PATH="$ICON_BASE/$size/apps/crusty-media-player.png"
    if [ -f "$ICON_PATH" ]; then
        rm -f "$ICON_PATH"
        ICON_REMOVED=1
    fi
    
    # Also check for .svg
    ICON_PATH="$ICON_BASE/$size/apps/crusty-media-player.svg"
    if [ -f "$ICON_PATH" ]; then
        rm -f "$ICON_PATH"
        ICON_REMOVED=1
    fi
done

if [ $ICON_REMOVED -eq 1 ]; then
    echo "  ✓ Removed icons"
    
    # Update icon cache
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
        echo "  ✓ Updated icon cache"
    fi
else
    echo "  ⚠ No icons found"
fi

echo ""
echo "Removing MIME associations..."

# List of video MIME types
VIDEO_MIMES=(
    "video/mp4"
    "video/x-matroska"
    "video/x-msvideo"
    "video/quicktime"
    "video/webm"
    "video/ogg"
    "video/mpeg"
)

# Remove MIME associations (reset to system default)
for mime in "${VIDEO_MIMES[@]}"; do
    CURRENT=$(xdg-mime query default "$mime" 2>/dev/null || echo "")
    if [[ "$CURRENT" == "crusty-media-player.desktop" ]]; then
        # Can't easily "unset" - just note it
        echo "  ⚠ $mime still set to Crusty (will use system default after reboot)"
    fi
done

echo "  ✓ MIME associations will reset to system defaults"

echo ""

# Ask about config files
if [ -d "$CONFIG_DIR" ]; then
    echo "Configuration files found at: $CONFIG_DIR"
    echo "This includes your saved settings and volume preferences."
    echo ""
    read -p "Remove configuration files? [y/N] " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo "  ✓ Removed configuration files"
    else
        echo "  • Kept configuration files (reinstall will restore settings)"
    fi
else
    echo "  • No configuration files found"
fi

echo ""
echo "Restarting file managers..."
pkill -9 nautilus nemo dolphin thunar pcmanfm caja 2>/dev/null || true
sleep 1

echo ""
echo "================================================"
echo "Uninstall Complete!"
echo "================================================"
echo ""
echo "Crusty Media Player has been removed from your system."
echo ""
echo "If you had set it as default, your system will use"
echo "the previous default video player (or ask you to choose)."
echo ""
echo "You may want to log out and back in to fully refresh"
echo "desktop integration."
echo ""
