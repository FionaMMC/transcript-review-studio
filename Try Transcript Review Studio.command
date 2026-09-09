#!/bin/zsh -l
set -eu
APP_DIR="${0:A:h}"
cd "$APP_DIR"
if [[ ! -x .venv/bin/python ]]; then
  echo "Run Setup Transcript Review Studio.command first."
  read -r "?Press Return to close."
  exit 1
fi
if ! .venv/bin/python scripts/practice.py; then
  echo "The practice setup did not finish. See the message above. Your research data was not used."
  read -r "?Press Return to close."
  exit 1
fi
exec .venv/bin/python scripts/launch.py --practice
