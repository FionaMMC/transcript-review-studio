#!/bin/zsh -l
set -e

APP_DIR="${0:A:h}"
cd "$APP_DIR"
exec .venv/bin/python scripts/launch.py
