#!/usr/bin/env python3
"""Clipping-Modul 1: Highlights in Stream-VODs finden und schneiden.

Signale:
  * Lautstaerke (Audio-RMS pro Sekunde, via ffmpeg)   -> Schreie, Lacher, Hype
  * Chat-Aktivitaet (optional, TwitchDownloader-JSON) -> Nachrichten pro Sekunde

Befehle:
  python3 clipper.py find VIDEO [--chat chat.json] [--top 10] [--out kandidaten.json]
  python3 clipper.py cut  VIDEO kandidaten.json [--vertical] [--outdir clips]

Benoetigt nur ffmpeg/ffprobe und Python 3 (keine Zusatzpakete).
"""
import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"FEHLER bei: {' '.join(cmd)}\n{res.stderr[-2000:]}")
    return res


def duration_of(video):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(video)]).stdout.strip()
    return float(out)


def loudness_per_second(video):
    """RMS-Pegel (dBFS) fuer jede Sekunde Audio."""
    af = ("aresample=16000,asetnsamples=n=16000:p=0,"
          "astats=metadata=1:reset=1,"
          "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-")
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video),
               "-vn", "-af", af, "-f", "null", "-"])
    levels = []
    for m in re.finditer(r"RMS_level=(-?[\d.]+|-inf)", res.stdout):
        v = m.group(1)
        levels.append(-100.0 if v == "-inf" else float(v))
    if not levels:
        sys.exit("FEHLER: Keine Audiospur gefunden oder Analyse leer.")
    return levels


def chat_per_second(chat_file, seconds):
    """Nachrichten pro Sekunde aus TwitchDownloader-Chat-JSON."""
    data = json.loads(Path(chat_file).read_text(encoding="utf-8"))
    counts = [0.0] * seconds
    for c in data.get("comments", []):
        t = int(c.get("content_offset_seconds", -1))
        if 0 <= t < seconds:
            counts[t] += 1
    return counts


def zscore(values):
    n = len(values)
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n) or 1.0
    return [(v - mean) / std for v in values]


def smooth(values, window):
    half = window // 2
    out = []
    for i in range(len(values)):
        seg = values[max(0, i - half): i + half + 1]
        out.append(sum(seg) / len(seg))
    return out


def find(args):
    video = Path(args.video)
    total = duration_of(video)
    loud = loudness_per_second(video)
    secs = len(loud)
    score = zscore(loud)
    if args.chat:
        chat = chat_per_second(args.chat, secs)
        # Chat reagiert meist 3-10 s verzoegert -> nach vorne verschieben
        lag = args.chat_lag
        chat = chat[lag:] + [0.0] * lag
        score = [a * (1 - args.chat_weight) + b * args.chat_weight
                 for a, b in zip(score, zscore(chat))]
    score = smooth(score, args.window)

    order = sorted(range(secs), key=lambda i: score[i], reverse=True)
    picks = []
    for i in order:
        if len(picks) >= args.top:
            break
        if score[i] < args.min_score:
            break
        if all(abs(i - p) >= args.min_gap for p in picks):
            picks.append(i)

    candidates = []
    for rank, peak in enumerate(picks, 1):
        start = max(0.0, peak - args.before)
        end = min(total, peak + args.after)
        candidates.append({"rang": rank, "peak_s": peak,
                           "start": round(start, 2), "ende": round(end, 2),
                           "score": round(score[peak], 3)})
    Path(args.out).write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    print(f"{len(candidates)} Kandidaten aus {secs}s Material -> {args.out}")
    for c in candidates:
        print(f"  #{c['rang']:>2}  {fmt(c['start'])} - {fmt(c['ende'])}  score {c['score']}")


def fmt(s):
    s = int(s)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def cut(args):
    video = Path(args.video)
    candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for c in candidates:
        out = outdir / f"clip_{c['rang']:02d}_{int(c['start'])}s.mp4"
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-ss", str(c["start"]), "-to", str(c["ende"]), "-i", str(video)]
        if args.vertical:
            # 9:16 fuer TikTok/Shorts/Reels: unscharfer Hintergrund + Bild mittig
            vf = ("split[a][b];"
                  "[a]scale=1080:1920:force_original_aspect_ratio=increase,"
                  "crop=1080:1920,boxblur=20:2[bg];"
                  "[b]scale=1080:-2[fg];"
                  "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
            cmd += ["-filter_complex", vf]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
        run(cmd)
        print(f"  geschnitten: {out}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("find", help="Highlight-Kandidaten finden")
    f.add_argument("video")
    f.add_argument("--chat", help="TwitchDownloader Chat-JSON (optional)")
    f.add_argument("--chat-weight", type=float, default=0.5)
    f.add_argument("--chat-lag", type=int, default=5, help="Chat-Verzoegerung in s")
    f.add_argument("--top", type=int, default=10)
    f.add_argument("--window", type=int, default=5, help="Glaettung in s")
    f.add_argument("--min-gap", type=int, default=60, help="Mindestabstand zwischen Clips in s")
    f.add_argument("--min-score", type=float, default=0.5)
    f.add_argument("--before", type=float, default=20, help="Sekunden vor dem Peak")
    f.add_argument("--after", type=float, default=10, help="Sekunden nach dem Peak")
    f.add_argument("--out", default="kandidaten.json")
    f.set_defaults(func=find)

    c = sub.add_parser("cut", help="Kandidaten schneiden")
    c.add_argument("video")
    c.add_argument("candidates")
    c.add_argument("--vertical", action="store_true", help="9:16 Hochformat")
    c.add_argument("--outdir", default="clips")
    c.set_defaults(func=cut)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
