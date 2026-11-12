"""Export eines Clips als 1080x1920-MP4: Zuschnitt mit Gesichtsverfolgung, Untertitel, Hook-Text."""
import subprocess
import time
from pathlib import Path

import numpy as np

from . import captions, facetrack, media

W, H, FPS = 1080, 1920, 30


def clip_words(words: list[dict], start: float, end: float) -> list[dict]:
    """Wörter des Ausschnitts, Zeiten relativ zum Clip-Anfang."""
    out = []
    for w in words:
        mid = (w["s"] + w["e"]) / 2
        if start <= mid <= end:
            out.append({"w": w["w"], "s": max(0.0, w["s"] - start), "e": max(0.05, min(end, w["e"]) - start)})
    return out


def export_clip(src, dst, start: float, end: float, info: dict, words: list[dict], *, template: str = "pop",
                layout: str = "auto", hook: str = "", hook_seconds: float = 2.5, progress=None) -> dict:
    """Rendert den Clip. Gibt {'seconds', 'layout', 'face_coverage'} zurück."""
    import cv2
    t0 = time.time()
    dur = max(0.2, end - start)
    sw, sh = info["width"], info["height"]
    # Sehr große Quellen (4K) vor dem Lesen verkleinern – spart Zeit, ohne sichtbaren Verlust bei 1080x1920.
    read_h = min(sh, 1920)
    read_h -= read_h % 2
    read_w = int(round(sw * read_h / sh / 2)) * 2
    src_ratio, out_ratio = read_w / read_h, W / H

    face = {"coverage": 0.0, "times": [0.0], "cx": [0.5]}
    if layout in ("auto", "face") and src_ratio > out_ratio * 1.02:
        if progress:
            progress(0.02, "Suche Gesichter …")
        face = facetrack.track(src, start, end, info)
    if layout == "auto":
        layout = "face" if face["coverage"] >= 0.4 else "blur"
    if src_ratio <= out_ratio * 1.02:
        layout = "fit"                                   # Quelle ist schon hochkant

    cap = captions.CaptionRenderer(clip_words(words, start, end), template)
    hook_img = captions.render_hook(hook) if hook and hook_seconds > 0 else None

    reader = media.popen(["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-an",
                          "-vf", f"fps={FPS},scale={read_w}:{read_h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    log = open(str(dst) + ".log", "wb")
    wargs = ["-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if info.get("has_audio"):
        wargs += ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-map", "0:v", "-map", "1:a:0",
                  "-c:a", "aac", "-b:a", "160k", "-ac", "2"]
    wargs += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-movflags", "+faststart", "-shortest", str(dst)]
    writer = media.popen(wargs, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)

    frame_bytes = read_w * read_h * 3
    total = max(1, int(round(dur * FPS)))
    crop_w = read_h * out_ratio                          # Breite des 9:16-Fensters in Quell-Pixeln
    scale = H / read_h
    ft, fx = np.array(face["times"]), np.array(face["cx"])
    n = 0
    try:
        while n < total:
            buf = reader.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(read_h, read_w, 3)
            t = n / FPS
            if layout == "face":
                cx = float(np.interp(t, ft, fx)) * read_w
                x0 = min(max(0.0, cx - crop_w / 2), read_w - crop_w)
                # Verschieben + Skalieren in einem Schritt (sub-pixel-genau, damit die Fahrt nicht ruckelt)
                m = np.float32([[scale, 0, -x0 * scale], [0, scale, 0]])
                out = cv2.warpAffine(frame, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            else:
                out = _blur_layout(cv2, frame, read_w, read_h)
            cap.draw(out, t)
            if hook_img is not None and t < hook_seconds:
                fade = min(1.0, (hook_seconds - t) / 0.3)
                pop = 0.9 + 0.1 * min(1.0, t / 0.12)
                captions.blend(out, hook_img, W / 2, H * 0.16, pop, fade)
            writer.stdin.write(out.tobytes())
            n += 1
            if progress and n % 15 == 0:
                progress(0.05 + 0.93 * n / total, f"Rendere Bild {n} von {total}")
    except BrokenPipeError:
        pass
    finally:
        reader.stdout.close()
        reader.wait()
        try:
            writer.stdin.close()
        except OSError:
            pass
        writer.wait()
        log.close()
    if writer.returncode != 0 or n == 0 or not Path(dst).exists():
        tail = Path(str(dst) + ".log").read_bytes()[-500:].decode("utf-8", "replace")
        raise media.MediaError("Der Export ist fehlgeschlagen. " + tail)
    Path(str(dst) + ".log").unlink(missing_ok=True)
    return {"seconds": round(time.time() - t0, 1), "layout": layout, "face_coverage": round(face["coverage"], 2),
            "frames": n}


def _blur_layout(cv2, frame, read_w, read_h):
    """Ganzes Bild mittig, dahinter dasselbe Bild unscharf und abgedunkelt."""
    cover = max(W / read_w, H / read_h)
    small_w, small_h = max(2, int(read_w * cover / 8)), max(2, int(read_h * cover / 8))
    bg = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_AREA)
    bg = cv2.GaussianBlur(bg, (0, 0), 6)
    bg = cv2.resize(bg, (small_w * 8, small_h * 8), interpolation=cv2.INTER_LINEAR)
    x = (bg.shape[1] - W) // 2
    y = (bg.shape[0] - H) // 2
    out = (bg[y: y + H, x: x + W] * 0.55).astype(np.uint8)
    if out.shape[0] != H or out.shape[1] != W:
        out = cv2.resize(out, (W, H))
    fit = min(W / read_w, H / read_h)
    fw, fh = int(read_w * fit) // 2 * 2, int(read_h * fit) // 2 * 2
    fg = cv2.resize(frame, (fw, fh), interpolation=cv2.INTER_AREA if fit < 1 else cv2.INTER_LINEAR)
    ox, oy = (W - fw) // 2, (H - fh) // 2
    out[oy: oy + fh, ox: ox + fw] = fg
    return np.ascontiguousarray(out)
