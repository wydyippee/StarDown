#!/bin/sh
# Zero-install launcher: ./run.sh list --user octocat
cd "$(dirname "$0")" || exit 1
python3 -c "import httpx, rich" 2>/dev/null || python3 -m pip install -q httpx "rich>=13"
PYTHONPATH="$PWD" exec python3 -m stardown "$@"
