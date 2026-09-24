#!/bin/bash
# Eenmalige installatie op macOS. Gebruik: dubbelklik "Installeren.command" of
#   bash mac/install.sh
set -e
cd "$(dirname "$0")/.."

PY=""
# python-rtmidi heeft kant-en-klare Mac-pakketten t/m Python 3.12, dus die heeft de voorkeur.
for cand in python3.12 python3.11 python3.10 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(not (3, 10) <= sys.version_info < (3, 13))' 2>/dev/null; then
    PY="$cand"; break
  fi
done

if [ -z "$PY" ]; then
  echo "Python 3.12 is nodig (de Python van macOS zelf is te oud, en voor 3.13+"
  echo "bestaat het MIDI-pakket nog niet kant-en-klaar)."
  echo "Installeer hem met Homebrew:   brew install python@3.12"
  echo "of download 'Python 3.12' via https://www.python.org/downloads/macos/"
  echo "en start dit script daarna opnieuw."
  exit 1
fi

echo "Python gevonden: $("$PY" --version)"
"$PY" -m venv .venv
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -r requirements.txt
mkdir -p "$HOME/Music/Piano Takes"
chmod +x mac/*.command
echo
echo "✔ Klaar. Sluit je piano aan en dubbelklik 'Piano opnemen.command'."
.venv/bin/python -m pianotool ports || true
