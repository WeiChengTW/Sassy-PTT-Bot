#!/bin/bash
set -e
cd "$(dirname "$0")"
export PYTHONPATH=.
export TRAVEL_STORAGE_ENABLED=true
export DB_PATH=data/chat.db
exec ./venv/bin/python line_bot/bot.py