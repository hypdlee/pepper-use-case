#!/bin/sh
# Starts the Care Dashboard (Python 3.8 or newer, nothing else to install).
cd "$(dirname "$0")" && exec python3 care_dashboard.py "$@"
