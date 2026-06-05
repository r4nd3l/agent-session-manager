#!/usr/bin/env bash
# Install the desktop launcher and icon for the current user.
set -euo pipefail

DATA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="eu.zengo.ClaudeSessionManager"

ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APPS_DIR="$HOME/.local/share/applications"

mkdir -p "$ICON_DIR" "$APPS_DIR"
cp "$DATA_DIR/icons/$APP_ID.svg" "$ICON_DIR/"

# Point Path= at wherever this checkout lives
sed "s|^Path=.*|Path=$(dirname "$DATA_DIR")|" "$DATA_DIR/$APP_ID.desktop" > "$APPS_DIR/$APP_ID.desktop"

update-desktop-database "$APPS_DIR" 2>/dev/null || true
gtk-update-icon-cache -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Installed: $APPS_DIR/$APP_ID.desktop"
echo "Installed: $ICON_DIR/$APP_ID.svg"
