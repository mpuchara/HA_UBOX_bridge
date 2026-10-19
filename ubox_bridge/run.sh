#!/bin/sh
set -eu
export PYTHONUNBUFFERED=1
exec /opt/ubox-venv/bin/python /app/bridge.py
