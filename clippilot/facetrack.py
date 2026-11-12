"""Gesichtsverfolgung: findet den Sprecher und liefert eine ruhige Kamerafahrt für den 9:16-Ausschnitt."""
import subprocess

import numpy as np

from . import config, media


def _detector(w: int, h: int):
    import cv2
    try:
        cv2.setLogLevel(0)          # Hinweise der Bibliothek nicht in die Konsole schreiben
    except Exception:
        pass
    return cv2.FaceDetectorYN.create(str(config.FACE_MODEL), "", (w, h), 0.6, 0.3, 50)


def _sample(src, start: float, dur: float, fps: float, info: dict, width: int = 480):
    """Liest verkleinerte Einzelbilder und gibt pro Bild die gefundenen Gesichter zurück."""
    w = width
    h = max(2, int(round(width * info["height"] / max(1, info["width"]) / 2)) * 2)
    det = _detector(w, h)
    p = media.popen(["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-an",
                     "-vf", f"fps={fps:.4f},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size, out = w * h * 3, []
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            _, faces = det.detect(frame)
            found = []
            if faces is not None:
                for f in faces:
                    found.append(((f[0] + f[2] / 2) / w, f[2] / w, float(f[-1])))   # (Mitte x, Breite, Sicherheit)
            out.append(found)
    finally:
        p.stdout.close()
        p.wait()
    return out


def _smooth(x: np.ndarray, sigma: float) -> np.ndarray:
    if len(x) < 3 or sigma <= 0:
        return x
    r = max(1, int(sigma * 3))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(x, r, mode="edge"), k, mode="valid")


def track(src, start: float, end: float, info: dict, fps: float = 4.0) -> dict:
    """Gibt {'coverage': Anteil der Bilder mit Gesicht, 'times': [...], 'cx': [...]} zurück (cx = 0..1)."""
    dur = max(0.1, end - start)
    try:
        samples = _sample(src, start, dur, fps, info)
    except Exception:
        samples = []
    n = len(samples)
    if n == 0:
        return {"coverage": 0.0, "times": [0.0], "cx": [0.5]}
    cx = np.full(n, np.nan)
    prev = None
    for i, faces in enumerate(samples):
        if not faces:
            continue
        biggest = max(f[1] for f in faces)
        cands = [f for f in faces if f[1] >= 0.6 * biggest]
        # nah am bisherigen Sprecher bleiben, statt zwischen Gesichtern zu springen
        best = min(cands, key=lambda f: abs(f[0] - prev)) if prev is not None else max(cands, key=lambda f: f[1])
        cx[i] = prev = best[0]
    have = ~np.isnan(cx)
    coverage = float(have.mean())
    if coverage == 0:
        return {"coverage": 0.0, "times": [0.0], "cx": [0.5]}
    idx = np.arange(n)
    cx = np.interp(idx, idx[have], cx[have])
    # Ausreißer glätten
    if n >= 5:
        pad = np.pad(cx, 2, mode="edge")
        cx = np.median(np.stack([pad[k: k + n] for k in range(5)]), axis=0)
    cx = _smooth(cx, 0.6 * fps)
    # Kamera bleibt stehen, solange sich der Kopf nur wenig bewegt, und zieht dann weich nach
    cam = np.empty(n)
    cam[0] = cx[0]
    for i in range(1, n):
        diff = cx[i] - cam[i - 1]
        cam[i] = cam[i - 1] + (diff * 0.3 if abs(diff) > 0.025 else 0.0)
    cam = _smooth(cam, 0.5 * fps)
    times = (idx + 0.5) / fps
    return {"coverage": coverage, "times": [float(t) for t in times], "cx": [float(v) for v in cam]}


def quick_focus(src, start: float, end: float, info: dict) -> float | None:
    """Grobe Position des Sprechers (für die Vorschau), aus wenigen Einzelbildern."""
    dur = max(0.5, end - start)
    try:
        samples = _sample(src, start, dur, 6.0 / dur, info)
    except Exception:
        return None
    xs = [max(f, key=lambda v: v[1])[0] for f in samples if f]
    if len(xs) < max(1, len(samples) // 3):
        return None
    return float(np.median(xs))
