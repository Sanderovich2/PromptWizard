#!/usr/bin/env bash
# Build the standalone Linux/macOS binary: dist/promptwizard
set -euo pipefail
cd "$(dirname "$0")/.."

PY="python3"
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
fi

echo "Installing PyInstaller if needed..."
"$PY" -m pip install --upgrade --disable-pip-version-check pyinstaller

echo "Building..."
"$PY" -m PyInstaller --noconfirm --clean packaging/promptwizard.spec

echo
echo "Built: dist/promptwizard"
