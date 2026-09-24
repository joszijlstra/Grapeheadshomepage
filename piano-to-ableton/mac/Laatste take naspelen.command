#!/bin/bash
# Dubbelklik: de piano speelt je laatste opname na.
cd "$(dirname "$0")/.."
.venv/bin/python -m pianotool play laatste "$@"
read -n 1 -s -r -p "Druk op een toets om dit venster te sluiten…"
