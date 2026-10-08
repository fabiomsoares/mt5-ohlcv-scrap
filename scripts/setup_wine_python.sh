#!/usr/bin/env bash
# One-time helper: installs Windows Python inside Wine and the runtime dependencies.
# Overrides: PYTHON_VERSION (default 3.11.9), WINE_PYTHON_EXE (default C:\Python311\python.exe)
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_VERSION="${PYTHON_VERSION:-3.11.9}"
WINE_PYTHON_EXE="${WINE_PYTHON_EXE:-C:\\Python311\\python.exe}"
INSTALLER="python-${PYTHON_VERSION}-amd64.exe"
URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${INSTALLER}"

if ! command -v wine >/dev/null 2>&1; then
    echo "ERROR: wine is not installed. Run: sudo apt install wine" >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Downloading $URL ..."
if command -v curl >/dev/null 2>&1; then
    curl -fL -o "$TMP_DIR/$INSTALLER" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -O "$TMP_DIR/$INSTALLER" "$URL"
else
    echo "ERROR: curl or wget is required." >&2
    exit 1
fi

echo "Installing Windows Python $PYTHON_VERSION inside Wine ..."
wine "$TMP_DIR/$INSTALLER" /quiet InstallAllUsers=1 TargetDir='C:\Python311' PrependPath=1 Include_test=0

echo "Installing runtime dependencies inside Wine Python ..."
wine "$WINE_PYTHON_EXE" -m pip install --upgrade pip
wine "$WINE_PYTHON_EXE" -m pip install -r requirements.txt

echo "Done. Run the scraper with ./run.sh (copy from run.sh.example)."
