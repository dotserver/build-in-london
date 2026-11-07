#!/bin/sh
# Rebuild everything from the raw data:  sh run_all.sh
set -e
cd "$(dirname "$0")"
python3 scripts/01_clean.py
python3 scripts/02_charts.py
python3 scripts/03_build_map.py
python3 scripts/04_export.py
