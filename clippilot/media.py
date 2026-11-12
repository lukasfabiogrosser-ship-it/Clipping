"""ffmpeg-Helfer: Infos lesen, Ton extrahieren, Lautstärke, Vorschau, Vorschaubilder."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

_FFMPEG = None
NO_WINDOW = 0x08000000 if os.name == "nt" else 0   # kein aufpoppendes Konsolenfenster unter Windows


class MediaError(Exception):
    pass


def ffmpeg() -> str:
    """Systemweites ffmpeg, sonst das mit imageio-ffmpeg mitgelieferte."""
    global _FFMPEG
    if _FFMPEG is None:
        found = shutil.which("ffmpeg")
        if not found:
            try:
                import imageio_ffmpeg
                found = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception as e:  # pragma: no cover
                raise MediaError("ffmpeg wurde nicht gefunden. Bitte ClipPilot über die Start-Datei starten.") from e
        _FFMPEG = found
    return _FFMPEG


def popen(args, **kw):
    return subprocess.Popen([ffmpeg(), "-hide_banner", "-nostdin", *args], creationflags=NO_WINDOW, **kw)


def run(args, **kw):
    return subprocess.run([ffmpeg(), "-hide_banner", "-nostdin", *args], capture_output=True,
                          creationflags=NO_WINDOW, **kw)


def probe(path) -> dict:
    """Dauer, Auflösung, Bildrate und Codecs aus der ffmpeg-Ausgabe lesen (kein ffprobe nötig)."""
    res = run(["-i", str(path)])
    text = res.stderr.decode("utf-8", "replace")
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0, "vcodec": "", "acodec": "", "has_audio": False}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    for line in text.splitlines():
        if "Video:" in line and not info["vcodec"] and "attached pic" not in line:
            info["vcodec"] = line.split("Video:")[1].strip().split()[0].strip(",")
            s = re.search(r"[ ,](\d{2,5})x(\d{2,5})[ ,\[]", line)
            if s:
                info["width"], info["height"] = int(s.group(1)), int(s.group(2))
            f = re.search(r"([\d.]+)\s*fps", line) or re.search(r"([\d.]+)\s*tbr", line)
            if f:
                info["fps"] = float(f.group(1))
            if re.search(r"rotate\s*:\s*(90|270)", text) or re.search(r"rotation of -?(90|270)", text):
                info["width"], info["height"] = info["height"], info["width"]
        elif "Audio:" in line and not info["acodec"]:
            info["acodec"] = line.split("Audio:")[1].strip().split()[0].strip(",")
            info["has_audio"] = True
    if not info["vcodec"] or not info["duration"]:
        raise MediaError("Diese Datei enthält kein lesbares Video.")
    return info


def browser_playable(path, info: dict) -> bool:
    ext = Path(path).suffix.lower()
    ok_audio = (not info["has_audio"]) or info["acodec"] in ("aac", "mp3")
    return ext in (".mp4", ".m4v", ".mov") and info["vcodec"] == "h264" and ok_audio and info["height"] <= 1080


def _with_progress(args, duration, progress):
    """ffmpeg starten und über -progress den Fortschritt (0..1) melden."""
    p = popen(["-y", *args, "-progress", "pipe:1", "-nostats"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    import threading
    err = []
    t = threading.Thread(target=lambda: err.append(p.stderr.read()), daemon=True)
    t.start()
    for raw in p.stdout:
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith("out_time_ms=") and duration > 0 and progress:
            try:
                progress(min(1.0, int(line.split("=")[1]) / 1e6 / duration))
            except ValueError:
                pass
    p.wait()
    t.join(timeout=5)
    if p.returncode != 0:
        tail = (err[0] if err else b"").decode("utf-8", "replace")[-600:]
        raise MediaError("ffmpeg-Fehler: " + tail)


def make_preview(src, dst, duration, progress=None):
    """Kleine, im Browser abspielbare Fassung (540p) für die Review-Ansicht."""
    _with_progress(["-i", str(src), "-vf", "scale=-2:'min(540,ih)'", "-c:v", "libx264", "-preset", "ultrafast",
                    "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-ac", "2",
                    "-movflags", "+faststart", str(dst)], duration, progress)


def extract_audio(src) -> np.ndarray:
    """Tonspur als 16-kHz-Mono-Float32 (für Whisper und Lautstärke)."""
    res = run(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
    if res.returncode != 0 or not res.stdout:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def loudness_per_second(audio: np.ndarray, sr: int = 16000) -> list[float]:
    """RMS-Pegel in dB für jede Sekunde."""
    n = len(audio) // sr
    if n == 0:
        return []
    chunks = audio[: n * sr].reshape(n, sr)
    rms = np.sqrt(np.mean(chunks.astype(np.float64) ** 2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-5))
    return [round(float(x), 2) for x in db]


def thumbnail(src, t: float, dst, width: int = 480):
    res = run(["-y", "-ss", f"{max(0, t):.2f}", "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2",
               "-q:v", "4", str(dst)])
    return res.returncode == 0 and Path(dst).exists()
