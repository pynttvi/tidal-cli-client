#!/usr/bin/env sh
set -eu

APP_NAME="tidal-cli-client"
INSTALL_ROOT="/usr/lib/$APP_NAME"
BIN_PATH="/usr/bin/tidal-cli"
VENV_DIR="$INSTALL_ROOT/.venv"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "python3-venv support is required." >&2
  exit 1
fi

if ! command -v mpv >/dev/null 2>&1; then
  echo "mpv is required." >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

mkdir -p "$INSTALL_ROOT"

# Copy app files.
cp -f "$REPO_ROOT/python_tidal_cli.py" "$INSTALL_ROOT/python_tidal_cli.py"
rm -rf "$INSTALL_ROOT/py_tidal_cli"
cp -R "$REPO_ROOT/py_tidal_cli" "$INSTALL_ROOT/py_tidal_cli"
cp -f "$REPO_ROOT/requirements.txt" "$INSTALL_ROOT/requirements.txt"

# Create isolated environment for runtime dependencies.
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python3" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python3" -m pip install -r "$INSTALL_ROOT/requirements.txt" >/dev/null

install -m 0755 "$REPO_ROOT/bin/tidal-cli" "$BIN_PATH"

echo "Installed $APP_NAME to $INSTALL_ROOT"
echo "Launcher installed at $BIN_PATH"
echo "Run: tidal-cli"
