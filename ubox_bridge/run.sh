#!/bin/sh
set -eu
export PYTHONUNBUFFERED=1
exec python3 /app/bridge.py
