#!/usr/bin/env bash
# Startet ClipPilot (Mac und Linux). Sucht ein passendes Python (3.10 bis 3.14) und übergibt an „ClipPilot starten.py“.
cd "$(dirname "$0")" || exit 1

ok() { "$1" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 14) else 1)' >/dev/null 2>&1; }

PY=""
CANDIDATES=""
for v in 3.13 3.12 3.14 3.11 3.10; do
  CANDIDATES="$CANDIDATES python$v /Library/Frameworks/Python.framework/Versions/$v/bin/python3 /opt/homebrew/bin/python$v /usr/local/bin/python$v"
done
for c in $CANDIDATES python3 python; do
  if command -v "$c" >/dev/null 2>&1 && ok "$c"; then PY="$c"; break; fi
done

if [ -z "$PY" ]; then
  echo
  echo "================================================================"
  FOUND=""
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      FOUND=$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null) && break
    fi
  done
  if [ -n "$FOUND" ]; then
    echo "  Gefunden: Python $FOUND. ClipPilot braucht Python 3.10 bis 3.14."
  else
    echo "  Python fehlt auf diesem Rechner."
  fi
  echo "  Bitte Python 3.13 installieren:"
  echo "  https://www.python.org/downloads/macos/  ->  \"Python 3.13.x\"  ->  macOS-Installer"
  echo "  Danach ClipPilot noch einmal starten."
  echo "================================================================"
  echo
  read -r -p "Zum Schliessen Enter druecken ..." _
  exit 1
fi
exec "$PY" "ClipPilot starten.py" "$@"
