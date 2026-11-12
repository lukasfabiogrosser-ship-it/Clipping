#!/usr/bin/env python3
"""ClipPilot starten – funktioniert auch per Doppelklick bzw. „Öffnen mit Python“.

Richtet beim ersten Start alles ein (eigene Umgebung im Ordner .venv) und startet dann die App.
Nur Python-Standardbibliothek, damit das mit jeder normalen Python-Installation läuft.
"""
import os
import shutil
import subprocess
import sys

MIN, MAX = (3, 10), (3, 14)        # neuere Python-Versionen: noch nicht alle Bausteine verfügbar
ROOT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(ROOT, ".venv")
WIN = os.name == "nt"
VPY = os.path.join(VENV, "Scripts", "python.exe") if WIN else os.path.join(VENV, "bin", "python")
CHECK = "import fastapi, uvicorn, faster_whisper, cv2, anthropic, yt_dlp, imageio_ffmpeg, fontTools, PIL"


def pause_and_exit(code: int):
    print()
    try:
        input("Zum Schließen Enter drücken …")
    except (EOFError, KeyboardInterrupt):
        pass
    sys.exit(code)


def version_of(python: str):
    try:
        out = subprocess.run([python, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
                             capture_output=True, text=True, timeout=60).stdout.split()
        return int(out[0]), int(out[1])
    except Exception:
        return None


def wrong_python(v):
    have = f"{v[0]}.{v[1]}"
    print("=" * 64)
    print(f"  Dieses Python hat die Version {have}.")
    if v > MAX:
        print("  Das ist zu neu: Einige Bausteine von ClipPilot gibt es dafür noch nicht.")
    else:
        print("  Das ist zu alt.")
    print("  Bitte installiere zusätzlich Python 3.13:")
    if sys.platform == "darwin":
        print("  https://www.python.org/downloads/macos/  → „Python 3.13.x“ → macOS-Installer")
    else:
        print("  https://www.python.org/downloads/  → „Python 3.13.x“")
    print("  Danach ClipPilot noch einmal starten. Dein altes Python kann bleiben.")
    print("=" * 64)
    pause_and_exit(1)


def main():
    os.chdir(ROOT)
    v = sys.version_info[:2]
    if not (MIN <= v <= MAX):
        wrong_python(v)

    # Eine vorhandene Umgebung mit unpassender Python-Version (z. B. von einem fehlgeschlagenen Versuch) neu anlegen
    if os.path.exists(VENV):
        vv = version_of(VPY) if os.path.exists(VPY) else None
        if vv is None or not (MIN <= vv <= MAX):
            print("Die alte Einrichtung passt nicht – ich lege sie neu an …")
            shutil.rmtree(VENV, ignore_errors=True)

    if not os.path.exists(VPY):
        print("Erste Einrichtung – das dauert ein paar Minuten …")
        if subprocess.run([sys.executable, "-m", "venv", VENV]).returncode != 0 or not os.path.exists(VPY):
            print("Die Einrichtung ist fehlgeschlagen (Python-Umgebung konnte nicht angelegt werden).")
            pause_and_exit(1)

    if subprocess.run([VPY, "-c", CHECK], capture_output=True).returncode != 0:
        print("Installiere Bausteine (nur beim ersten Start oder nach einem Update, ca. 1 GB) …")
        subprocess.run([VPY, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        if subprocess.run([VPY, "-m", "pip", "install", "--quiet", "-r", "requirements.txt"]).returncode != 0:
            print()
            print("Die Installation ist fehlgeschlagen. Bitte Internetverbindung prüfen und noch einmal starten.")
            print("Wenn es wieder scheitert: die Meldungen oben abfotografieren und an Claude schicken.")
            pause_and_exit(1)

    try:
        code = subprocess.run([VPY, "-m", "clippilot", *sys.argv[1:]]).returncode
    except KeyboardInterrupt:
        code = 0
    if code != 0:
        print("ClipPilot wurde mit einem Fehler beendet (siehe Meldungen oben).")
        pause_and_exit(code)


if __name__ == "__main__":
    main()
