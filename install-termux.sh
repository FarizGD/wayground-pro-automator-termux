#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

pkg update
pkg install -y python
python -m pip install --upgrade pip
python -m pip install -r requirements-termux.txt

echo
echo "Termux TUI dependencies installed."
echo "Run: python src/tui.py"
