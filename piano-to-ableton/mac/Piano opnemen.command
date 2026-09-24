#!/bin/bash
# Dubbelklik: luistert naar de piano en slaat elke melodie op in ~/Music/Piano Takes.
cd "$(dirname "$0")/.."
.venv/bin/python -m pianotool record --bpm "${BPM:-100}" "$@"
