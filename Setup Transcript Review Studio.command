#!/bin/zsh -l
set -u

APP_DIR="${0:A:h}"
cd "$APP_DIR"
export NEXT_TELEMETRY_DISABLED=1

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This installer supports Apple Silicon Macs. Other platforms are experimental; see README."
  read -r "?Press Return to close."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it, then run setup again."
  read -r "?Press Return to close."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 22 or newer is required. Install it, then run setup again."
  read -r "?Press Return to close."
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Python 3.11 or newer is required. Your Python is: $(python3 --version 2>&1)"
  read -r "?Press Return to close."
  exit 1
fi

if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 22 || (major === 22 && minor >= 13) ? 0 : 1)'; then
  echo "Node.js 22.13 or newer is required. Your Node.js is: $(node --version 2>&1)"
  read -r "?Press Return to close."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "FFmpeg is required. On macOS with Homebrew, run: brew install ffmpeg"
  read -r "?Press Return to close."
  exit 1
fi

echo "Setting up the private local processing environment…"
if ! python3 -m venv .venv; then
  echo "Could not create the isolated Python environment."
  read -r "?Press Return to close."
  exit 1
fi
if ! .venv/bin/python -m pip install --upgrade pip; then
  echo "Could not prepare Python package installation. Check your internet connection and try again."
  read -r "?Press Return to close."
  exit 1
fi
if ! .venv/bin/python -m pip install -r backend/requirements.txt; then
  echo "Could not install the local transcription service. See the error above."
  read -r "?Press Return to close."
  exit 1
fi
if ! npm ci; then
  echo "Could not install the interface dependencies. See the error above."
  read -r "?Press Return to close."
  exit 1
fi
if [[ -e "$APP_DIR/.git" ]] && [[ "$(git rev-parse --show-toplevel 2>/dev/null)" == "$APP_DIR" ]]; then
  git config core.hooksPath .githooks
  chmod +x .githooks/pre-commit .githooks/pre-push
fi
if ! npm run lint || ! npm run build; then
  echo "Setup installed the dependencies, but the product validation failed. See the error above."
  read -r "?Press Return to close."
  exit 1
fi

echo ""
echo "✓ Setup complete. Double-click ‘Open Transcript Review Studio.command’ to begin."
read -r "?Press Return to close."
