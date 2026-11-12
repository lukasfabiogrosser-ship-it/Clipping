@echo off
rem Windows: Diese Datei doppelklicken, um ClipPilot zu starten.
title ClipPilot
cd /d "%~dp0"

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto have_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto have_python

echo.
echo Python fehlt auf diesem Rechner. ClipPilot braucht Python 3.10 oder neuer.
where winget >nul 2>nul
if errorlevel 1 goto manual_python
echo Ich installiere Python jetzt automatisch. Bitte eventuelle Nachfragen bestaetigen.
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Fertig. Bitte dieses Fenster schliessen und "ClipPilot starten" noch einmal doppelklicken.
pause
exit /b 0

:manual_python
echo Bitte Python von https://www.python.org/downloads/ installieren.
echo Wichtig: beim Installieren den Haken bei "Add python.exe to PATH" setzen.
echo Danach "ClipPilot starten" noch einmal doppelklicken.
pause
exit /b 1

:have_python
if exist ".venv\Scripts\python.exe" goto check_packages
echo Erste Einrichtung - das dauert ein paar Minuten ...
%PY% -m venv .venv
if errorlevel 1 goto failed

:check_packages
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, faster_whisper, cv2, anthropic, yt_dlp, imageio_ffmpeg, fontTools, PIL" >nul 2>nul
if not errorlevel 1 goto run
echo Installiere Bausteine - nur beim ersten Start oder nach einem Update ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto failed

:run
".venv\Scripts\python.exe" -m clippilot
echo.
echo ClipPilot wurde beendet.
pause
exit /b 0

:failed
echo.
echo Die Einrichtung ist fehlgeschlagen. Bitte Internetverbindung pruefen und noch einmal starten.
pause
exit /b 1
