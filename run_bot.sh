#!/bin/bash
set -e
cd "$(dirname "$0")"
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 PYTHONUTF8=1
export PYTHONPATH=.
export TRAVEL_STORAGE_ENABLED=true
export DB_PATH=data/chat.db
exec ./venv/bin/python line_bot/bot.py