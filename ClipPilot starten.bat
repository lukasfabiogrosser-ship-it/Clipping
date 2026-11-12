@echo off
rem Windows: Diese Datei doppelklicken, um ClipPilot zu starten.
title ClipPilot
cd /d "%~dp0"

rem Passendes Python suchen (3.10 bis 3.14 - neuere Versionen werden noch nicht von allen Bausteinen unterstuetzt)
for %%V in (3.13 3.12 3.14 3.11 3.10) do (
  py -%%V -c "import sys" >nul 2>nul && ( py -%%V "ClipPilot starten.py" %* & exit /b )
)
python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 14) else 1)" >nul 2>nul
if not errorlevel 1 ( python "ClipPilot starten.py" %* & exit /b )

echo.
echo Es fehlt ein passendes Python. ClipPilot braucht Python 3.10 bis 3.14.
where winget >nul 2>nul
if errorlevel 1 goto manual_python
echo Ich installiere Python 3.13 jetzt automatisch. Bitte eventuelle Nachfragen bestaetigen.
winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements
echo.
echo Fertig. Bitte dieses Fenster schliessen und "ClipPilot starten" noch einmal doppelklicken.
pause
exit /b 0

:manual_python
echo Bitte Python 3.13 von https://www.python.org/downloads/ installieren.
echo Wichtig: beim Installieren den Haken bei "Add python.exe to PATH" setzen.
echo Danach "ClipPilot starten" noch einmal doppelklicken.
pause
exit /b 1
