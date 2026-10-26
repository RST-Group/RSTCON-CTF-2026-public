#!/usr/bin/env bash
# Reproduce the whole analysis from the distributed log (../dist/*.log.gz).
# Network access is needed for the opendbc DBC, OpenStreetMap (Overpass) and
# Nominatim; downloads are cached in ../scratch/.
set -euo pipefail
cd "$(dirname "$0")"
export MPLBACKEND=Agg   # save plots without opening windows

python3 decode_path.py    # unpack log, decode CAN, dead-reckon → path_data.csv
python3 locate_start.py   # rigid single-rotation search (first attempt)
python3 compare_heading.py # why the steering path drifts: steering vs gyro vs wheel-difference heading
python3 snap_path.py       # gyro heading + drift-corrected road snapping (final answer)
