"""Hintergrund-Aufgaben: Import, Transkription, Analyse, Export, Texte. Ein Arbeiter, eine Warteschlange."""
import json
import queue
import threading
import time
import traceback
from pathlib import Path

from . import config, db, facetrack, highlights, media, render, texts, transcribe

_q: "queue.Queue[int]" = queue.Queue()
_started = False

LABELS = {"process": "Video verarbeiten", "download": "Video laden", "analyze": "Highlights suchen",
          "export": "Clip exportieren", "texts": "Texte schreiben"}


def start():
    global _started
    if _started:
        return
    _started = True
    # Aufgaben, die beim letzten Beenden noch liefen, sauber als abgebrochen markieren
    for j in db.q("SELECT id, project_id FROM jobs WHERE status IN ('running','queued')"):
        db.update("jobs", j["id"], status="error", error="Abgebrochen, weil ClipPilot beendet wurde.",
                  finished_at=db.now())
    db.run("UPDATE projects SET status='error', error='Die Verarbeitung wurde unterbrochen. Bitte neu starten.' "
           "WHERE status='processing'")
    threading.Thread(target=_worker, daemon=True, name="clippilot-worker").start()


def enqueue(kind: str, project_id=None, clip_id=None, payload=None) -> int:
    jid = db.insert("jobs", kind=kind, project_id=project_id, clip_id=clip_id,
                    payload=json.dumps(payload or {}), status="queued", message="Wartet …", created_at=db.now())
    _q.put(jid)
    return jid


def _worker():
    while True:
        jid = _q.get()
        job = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
        if not job or job["status"] != "queued":
            continue
        t0 = time.time()
        db.update("jobs", jid, status="running", started_at=db.now(), message="Startet …")
        last = [0.0]

        def progress(p: float, msg: str | None = None, _jid=jid):
            now = time.time()
            if now - last[0] < 0.4 and p < 1:
                return
            last[0] = now
            fields = {"progress": round(max(0.0, min(1.0, p)), 4)}
            if msg:
                fields["message"] = msg
            db.update("jobs", _jid, **fields)

        try:
            HANDLERS[job["kind"]](job, progress)
            db.update("jobs", jid, status="done", progress=1, message="Fertig", finished_at=db.now(),
                      seconds=round(time.time() - t0, 1))
        except Exception as e:  # noqa: BLE001 – jede Störung landet als lesbare Meldung beim Nutzer
            traceback.print_exc()
            msg = str(e) if isinstance(e, (media.MediaError, transcribe.TranscribeError)) else f"{type(e).__name__}: {e}"
            db.update("jobs", jid, status="error", error=msg[:800], finished_at=db.now(),
                      seconds=round(time.time() - t0, 1))
            if job["kind"] in ("process", "download", "analyze") and job["project_id"]:
                db.update("projects", job["project_id"], status="error", error=msg[:800])


# ---------- Projekt: importieren, transkribieren, Highlights suchen ----------

def source_path(project: dict) -> Path:
    return config.project_dir(project["id"]) / project["filename"]


def load_transcript(pid: int) -> dict:
    f = config.project_dir(pid) / "transcript.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"language": "", "segments": [], "words": []}


def load_loudness(pid: int) -> list[float]:
    f = config.project_dir(pid) / "loudness.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def _process(job, progress):
    pid = job["project_id"]
    project = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    cfg = config.load_settings()
    pdir = config.project_dir(pid)
    src = source_path(project)
    db.update("projects", pid, status="processing", error=None)

    progress(0.01, "Lese Video-Infos …")
    info = media.probe(src)
    db.update("projects", pid, duration=info["duration"], width=info["width"], height=info["height"], fps=info["fps"])

    if not media.browser_playable(src, info):
        progress(0.02, "Erstelle Vorschau für den Browser …")
        media.make_preview(src, pdir / "preview.mp4", info["duration"],
                           lambda p: progress(0.02 + 0.13 * p, "Erstelle Vorschau für den Browser …"))
        db.update("projects", pid, preview_file="preview.mp4")
    media.thumbnail(src, min(info["duration"] * 0.2, 30), pdir / "thumb.jpg")

    progress(0.16, "Lese Tonspur …")
    audio = media.extract_audio(src)
    loud = media.loudness_per_second(audio)
    (pdir / "loudness.json").write_text(json.dumps(loud), encoding="utf-8")

    dev = transcribe.device_info()["label"]
    progress(0.2, f"Lade Sprachmodell „{cfg['whisper_model']}“ …")
    tr = transcribe.transcribe(audio, cfg["whisper_model"], cfg["language"],
                               lambda p: progress(0.2 + 0.6 * p, f"Transkribiere ({dev}) … {int(p * 100)} %"))
    del audio
    (pdir / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")
    db.update("projects", pid, language=tr["language"])

    _find_highlights(pid, info, tr, loud, cfg, progress, 0.82)
    db.update("projects", pid, status="ready")


def _analyze(job, progress):
    pid = job["project_id"]
    project = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    db.update("projects", pid, status="processing", error=None)
    info = media.probe(source_path(project))
    _find_highlights(pid, info, load_transcript(pid), load_loudness(pid), config.load_settings(), progress, 0.05)
    db.update("projects", pid, status="ready")


def _find_highlights(pid, info, tr, loud, cfg, progress, p0):
    project = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    progress(p0, "Suche die besten Momente …")
    found, engine, note = highlights.find(tr, loud, info["duration"], cfg)
    if not tr.get("words"):
        note = "Im Video wurde keine Sprache erkannt. Du kannst Clips trotzdem von Hand anlegen."
    # Unberührte alte Vorschläge ersetzen; alles, was du schon angenommen oder bearbeitet hast, bleibt.
    db.run("DELETE FROM clips WHERE project_id=? AND status='candidate' AND origin='ai'", (pid,))
    src = source_path(project)
    for k, c in enumerate(found):
        progress(p0 + (0.98 - p0) * (k + 1) / max(1, len(found)), "Bereite Vorschläge vor …")
        fx = facetrack.quick_focus(src, c["start"], c["end"], info)
        db.insert("clips", project_id=pid, idx=k + 1, title=c["title"] or f"Clip {k + 1}", start=c["start"],
                  end=c["end"], ai_start=c["start"], ai_end=c["end"], ai_score=c["score"], reason_tag=c["tag"],
                  reason=c["reason"], hook=c["hook"], hook_enabled=1, status="candidate",
                  template=cfg["caption_template"], layout=cfg["layout"], focus_x=fx, origin="ai",
                  created_at=db.now())
    db.update("projects", pid, analysis_engine=engine, analysis_note=note)


def _download(job, progress):
    """Video von einem Link laden (yt-dlp) und danach wie einen Upload verarbeiten."""
    import yt_dlp
    pid = job["project_id"]
    project = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    pdir = config.project_dir(pid)
    db.update("projects", pid, status="processing", error=None)

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                p = d.get("downloaded_bytes", 0) / total
                progress(0.3 * p, f"Lade Video … {int(p * 100)} %")

    opts = {"outtmpl": str(pdir / "source.%(ext)s"), "noplaylist": True, "quiet": True, "no_warnings": True,
            "format": "bv*[height<=1080]+ba/b[height<=1080]/b", "merge_output_format": "mp4",
            "ffmpeg_location": media.ffmpeg(), "progress_hooks": [hook], "retries": 3}
    progress(0.0, "Verbinde …")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            meta = ydl.extract_info(project["source_url"], download=True)
    except Exception as e:  # noqa: BLE001
        raise media.MediaError(f"Der Link konnte nicht geladen werden: {str(e)[:300]}") from e
    files = sorted(pdir.glob("source.*"), key=lambda f: f.stat().st_size, reverse=True)
    if not files:
        raise media.MediaError("Der Download hat keine Videodatei geliefert.")
    title = (meta or {}).get("title") or project["title"]
    db.update("projects", pid, filename=files[0].name, title=title[:200])

    def sub(p, msg=None):
        progress(0.3 + 0.7 * p, msg)
    _process(job, sub)


# ---------- Clip: exportieren, Texte ----------

def clip_text(clip: dict, tr: dict) -> str:
    return " ".join(w["w"] for w in render.clip_words(tr.get("words", []), clip["start"], clip["end"]))


def _export(job, progress):
    cid = job["clip_id"]
    clip = db.one("SELECT * FROM clips WHERE id=?", (cid,))
    project = db.one("SELECT * FROM projects WHERE id=?", (clip["project_id"],))
    cfg = config.load_settings()
    pdir = config.project_dir(project["id"])
    (pdir / "exports").mkdir(exist_ok=True)
    src = source_path(project)
    info = media.probe(src)
    tr = load_transcript(project["id"])
    name = f"clip_{cid}.mp4"
    tmp = pdir / "exports" / f"clip_{cid}.tmp.mp4"
    res = render.export_clip(
        src, tmp, clip["start"], clip["end"], info, tr.get("words", []),
        template=clip["template"] or cfg["caption_template"], layout=clip["layout"] or cfg["layout"],
        hook=(clip["hook"] or "") if clip["hook_enabled"] else "", hook_seconds=float(cfg["hook_seconds"]),
        progress=lambda p, m=None: progress(p * 0.95, m))
    tmp.replace(pdir / "exports" / name)
    media.thumbnail(pdir / "exports" / name, min(1.0, (clip["end"] - clip["start"]) / 2),
                    pdir / "exports" / f"clip_{cid}.jpg", 360)
    status = clip["status"] if clip["status"] in ("done", "posted") else "done"
    db.update("clips", cid, export_file=f"exports/{name}", export_seconds=res["seconds"], exported_at=db.now(),
              export_stale=0, status=status)
    if not clip["texts"]:
        progress(0.96, "Schreibe Titel und Beschreibung …")
        _write_texts(clip, project, tr)


def _write_texts(clip, project, tr):
    rules = ""
    if clip.get("campaign_id"):
        camp = db.one("SELECT rules FROM campaigns WHERE id=?", (clip["campaign_id"],))
        rules = (camp or {}).get("rules") or ""
    data, engine, note = texts.generate(clip_text(clip, tr), clip["hook"] or "", clip["title"] or "",
                                        project["language"] or "", rules)
    data["_note"] = note
    db.update("clips", clip["id"], texts=data, texts_engine=engine)


def _texts(job, progress):
    clip = db.one("SELECT * FROM clips WHERE id=?", (job["clip_id"],))
    project = db.one("SELECT * FROM projects WHERE id=?", (clip["project_id"],))
    progress(0.2, "Schreibe Titel und Beschreibung …")
    _write_texts(clip, project, load_transcript(project["id"]))


HANDLERS = {"process": _process, "analyze": _analyze, "download": _download, "export": _export, "texts": _texts}
