#!/usr/bin/env bash
# Startet ClipPilot (Mac und Linux). Beim ersten Mal wird alles Noetige eingerichtet.
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo
  echo "Python (Version 3.10 oder neuer) fehlt auf diesem Rechner."
  echo "Bitte von https://www.python.org/downloads/ installieren und ClipPilot danach noch einmal starten."
  echo
  read -r -p "Zum Schliessen Enter druecken ..." _
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Erste Einrichtung - das dauert ein paar Minuten ..."
  "$PY" -m venv .venv || { echo "Die Einrichtung ist fehlgeschlagen."; read -r -p "Enter ..." _; exit 1; }
fi
if ! .venv/bin/python -c 'import fastapi, uvicorn, faster_whisper, cv2, anthropic, yt_dlp, imageio_ffmpeg, fontTools, PIL' >/dev/null 2>&1; then
  echo "Installiere Bausteine (nur beim ersten Start oder nach einem Update) ..."
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt || {
    echo "Die Installation ist fehlgeschlagen. Bitte Internetverbindung pruefen und noch einmal starten."
    read -r -p "Zum Schliessen Enter druecken ..." _
    exit 1
  }
fi
exec .venv/bin/python -m clippilot "$@"
