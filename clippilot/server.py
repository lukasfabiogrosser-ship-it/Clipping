"""Web-Server (nur auf diesem Rechner erreichbar) mit allen Schnittstellen für die Oberfläche."""
import json
import os
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, ai, captions, config, db, highlights, jobs, media, sample, stats, texts, transcribe

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".flv", ".ts", ".mpg", ".mpeg", ".wmv"}
STATUSES = ("candidate", "editing", "done", "posted", "rejected")

@asynccontextmanager
async def _lifespan(_app):
    config.ensure_dirs()
    db.init()
    jobs.start()
    yield


app = FastAPI(title="ClipPilot", docs_url=None, redoc_url=None, lifespan=_lifespan)


def fail(code: int, msg: str):
    raise HTTPException(status_code=code, detail=msg)


@app.exception_handler(HTTPException)
async def _http_error(_, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def _any_error(_, exc: Exception):
    return JSONResponse({"error": f"Unerwarteter Fehler: {type(exc).__name__}: {exc}"}, status_code=500)


# ---------------------------------------------------------------- Helfer

def get_project(pid: int) -> dict:
    p = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        fail(404, "Projekt nicht gefunden.")
    return p


def get_clip(cid: int) -> dict:
    c = db.one("SELECT * FROM clips WHERE id=?", (cid,))
    if not c:
        fail(404, "Clip nicht gefunden.")
    return c


def clip_out(c: dict, led=None) -> dict:
    c = dict(c)
    c["texts"] = json.loads(c["texts"]) if c.get("texts") else None
    c["score"] = c["user_score"] if c["user_score"] is not None else (c["ai_score"] or 0)
    c["duration"] = round(c["end"] - c["start"], 2)
    c["has_export"] = bool(c["export_file"])
    c["reason_label"] = highlights.TAGS.get(c.get("reason_tag") or "", "")
    c["posts"] = db.q("SELECT p.*, k.name AS campaign_name FROM posts p LEFT JOIN campaigns k ON k.id=p.campaign_id "
                      "WHERE p.clip_id=? ORDER BY p.id", (c["id"],))
    if led is not None:
        c["earned"] = round(led["by_clip"].get(c["id"], 0.0), 2)
        for p in c["posts"]:
            p["earned"] = round(led["by_post"].get(p["id"], 0.0), 2)
    c["views"] = sum(p["views"] or 0 for p in c["posts"])
    return c


def project_out(p: dict) -> dict:
    p = dict(p)
    rows = db.q("SELECT status, COUNT(*) AS n FROM clips WHERE project_id=? GROUP BY status", (p["id"],))
    p["clip_counts"] = {r["status"]: r["n"] for r in rows}
    job = db.one("SELECT * FROM jobs WHERE project_id=? AND clip_id IS NULL ORDER BY id DESC LIMIT 1", (p["id"],))
    p["job"] = job if job and job["status"] in ("queued", "running") else None
    return p


async def body(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        fail(400, "Ungültige Anfrage.")
    if not isinstance(data, dict):
        fail(400, "Ungültige Anfrage.")
    return data


def _num(v, name, lo=None, hi=None, integer=False):
    try:
        x = int(v) if integer else float(v)
    except (TypeError, ValueError):
        fail(400, f"„{name}“ muss eine Zahl sein.")
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        fail(400, f"„{name}“ liegt außerhalb des erlaubten Bereichs.")
    return x


# ---------------------------------------------------------------- Allgemein

@app.get("/api/meta")
def meta():
    return {
        "version": __version__,
        "templates": [{"id": k, "label": v["label"], "desc": v["desc"], "upper": v["upper"],
                       "max_words": v["max_words"], "max_chars": v["max_chars"]} for k, v in captions.TEMPLATES.items()],
        "platforms": list(texts.PLATFORMS.values()), "text_platforms": texts.PLATFORMS,
        "tags": highlights.TAGS, "ai_models": config.AI_MODELS, "whisper_models": config.WHISPER_MODELS,
        "device": transcribe.device_info()["label"],
    }


@app.get("/api/state")
def state():
    cut = (datetime.now() - timedelta(seconds=20)).isoformat(timespec="seconds")
    js = db.q("SELECT j.*, p.title AS project_title, c.title AS clip_title FROM jobs j "
              "LEFT JOIN projects p ON p.id=j.project_id LEFT JOIN clips c ON c.id=j.clip_id "
              "WHERE j.status IN ('queued','running') OR j.finished_at >= ? ORDER BY j.id", (cut,))
    for j in js:
        j["label"] = jobs.LABELS.get(j["kind"], j["kind"])
    return {"jobs": js, "hud": stats.hud(), "sample": sample.exists(), "has_api_key": ai.has_key()}


@app.get("/api/settings")
def get_settings():
    return config.public_settings()


@app.post("/api/settings")
async def post_settings(request: Request):
    data = await body(request)
    patch = {}
    if "anthropic_api_key" in data:
        patch["anthropic_api_key"] = str(data["anthropic_api_key"] or "").strip()
    if "ai_model" in data:
        if data["ai_model"] not in [m["id"] for m in config.AI_MODELS]:
            fail(400, "Unbekanntes KI-Modell.")
        patch["ai_model"] = data["ai_model"]
    if "whisper_model" in data:
        if data["whisper_model"] not in [m["id"] for m in config.WHISPER_MODELS]:
            fail(400, "Unbekanntes Sprachmodell.")
        patch["whisper_model"] = data["whisper_model"]
    if "language" in data:
        if data["language"] not in ("auto", "de", "en"):
            fail(400, "Unbekannte Sprache.")
        patch["language"] = data["language"]
    if "caption_template" in data:
        if data["caption_template"] not in captions.TEMPLATES:
            fail(400, "Unbekannte Untertitel-Vorlage.")
        patch["caption_template"] = data["caption_template"]
    if "layout" in data:
        if data["layout"] not in ("auto", "face", "blur"):
            fail(400, "Unbekanntes Layout.")
        patch["layout"] = data["layout"]
    ranges = {"clip_min_s": (5, 170, True), "clip_max_s": (10, 180, True), "num_suggestions": (1, 30, True),
              "hook_seconds": (0, 10, False), "goal_clips_per_day": (0, 100, True),
              "goal_month_eur": (0, 1_000_000, False), "manual_minutes_per_clip": (1, 600, False)}
    for k, (lo, hi, integer) in ranges.items():
        if k in data:
            patch[k] = _num(data[k], k, lo, hi, integer)
    cur = config.load_settings()
    if patch.get("clip_min_s", cur["clip_min_s"]) >= patch.get("clip_max_s", cur["clip_max_s"]):
        fail(400, "Die Mindestlänge muss kleiner sein als die Höchstlänge.")
    config.save_settings(patch)
    return config.public_settings()


@app.post("/api/settings/test-key")
def test_key():
    return ai.test_key()


# ---------------------------------------------------------------- Projekte

@app.get("/api/projects")
def list_projects():
    return [project_out(p) for p in db.q("SELECT * FROM projects ORDER BY id DESC")]


@app.put("/api/projects/upload")
async def upload(request: Request, name: str):
    ext = Path(name).suffix.lower()
    if ext not in VIDEO_EXT:
        fail(400, f"Dieses Dateiformat wird nicht unterstützt ({ext or 'ohne Endung'}). Erlaubt: MP4, MOV, MKV, WEBM u. a.")
    title = Path(name).stem[:200] or "Video"
    pid = db.insert("projects", title=title, source_kind="upload", filename=f"source{ext}", status="imported",
                    created_at=db.now())
    dst = config.project_dir(pid) / f"source{ext}"
    size = 0
    try:
        with open(dst, "wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                size += len(chunk)
    except Exception:
        _delete_project(pid)
        fail(400, "Der Upload wurde unterbrochen.")
    if size == 0:
        _delete_project(pid)
        fail(400, "Die Datei ist leer.")
    try:
        media.probe(dst)
    except media.MediaError as e:
        _delete_project(pid)
        fail(400, str(e))
    db.update("projects", pid, status="processing")
    jobs.enqueue("process", project_id=pid)
    return project_out(get_project(pid))


@app.post("/api/projects/link")
async def link(request: Request):
    data = await body(request)
    url = str(data.get("url") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        fail(400, "Bitte einen vollständigen Link angeben (beginnt mit https://).")
    if not data.get("rights_confirmed"):
        fail(400, "Bitte bestätige, dass du die Rechte oder eine Kampagnenfreigabe für dieses Material hast.")
    pid = db.insert("projects", title=url[:120], source_kind="link", source_url=url, filename="source.mp4",
                    status="processing", created_at=db.now())
    jobs.enqueue("download", project_id=pid)
    return project_out(get_project(pid))


@app.get("/api/projects/{pid}")
def project_detail(pid: int):
    p = project_out(get_project(pid))
    led = stats.ledger()
    p["clips"] = [clip_out(c, led) for c in
                  db.q("SELECT * FROM clips WHERE project_id=? ORDER BY "
                       "COALESCE(user_score, ai_score) DESC, id", (pid,))]
    return p


@app.get("/api/projects/{pid}/transcript")
def project_transcript(pid: int):
    get_project(pid)
    tr = jobs.load_transcript(pid)
    return {"language": tr.get("language"), "words": tr.get("words", []),
            "sentences": transcribe.sentences(tr.get("words", [])), "loudness": jobs.load_loudness(pid)}


@app.get("/api/projects/{pid}/video")
def project_video(pid: int):
    p = get_project(pid)
    if not p["filename"]:
        fail(404, "Zu diesem Projekt gibt es kein Video.")
    f = config.project_dir(pid) / (p["preview_file"] or p["filename"])
    if not f.exists():
        fail(404, "Die Videodatei fehlt.")
    return FileResponse(f, media_type="video/mp4")


@app.get("/api/projects/{pid}/thumb")
def project_thumb(pid: int, t: float | None = None):
    p = get_project(pid)
    pdir = config.project_dir(pid)
    if t is None:
        f = pdir / "thumb.jpg"
    else:
        (pdir / "thumbs").mkdir(exist_ok=True)
        f = pdir / "thumbs" / f"{int(t * 10)}.jpg"
        if not f.exists() and p["filename"]:
            media.thumbnail(pdir / p["filename"], t, f, 360)
    if not f.exists():
        fail(404, "Kein Vorschaubild.")
    return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@app.post("/api/projects/{pid}/analyze")
def analyze(pid: int):
    p = get_project(pid)
    if p["status"] == "processing":
        fail(409, "Dieses Projekt wird gerade verarbeitet.")
    if not (config.project_dir(pid) / "transcript.json").exists():
        db.update("projects", pid, status="processing", error=None)
        jobs.enqueue("process", project_id=pid)
    else:
        db.update("projects", pid, status="processing", error=None)
        jobs.enqueue("analyze", project_id=pid)
    return project_out(get_project(pid))


@app.post("/api/projects/{pid}/clips")
async def add_clip(pid: int, request: Request):
    p = get_project(pid)
    data = await body(request)
    start = _num(data.get("start"), "Start", 0, p["duration"])
    end = _num(data.get("end"), "Ende", 0, p["duration"])
    if end - start < 1:
        fail(400, "Ein Clip muss mindestens eine Sekunde lang sein.")
    cfg = config.load_settings()
    n = db.one("SELECT COUNT(*) AS n FROM clips WHERE project_id=?", (pid,))["n"]
    cid = db.insert("clips", project_id=pid, idx=n + 1, title=str(data.get("title") or f"Eigener Clip {n + 1}"),
                    start=start, end=end, ai_score=0, reason="Von dir angelegt", hook="", hook_enabled=0,
                    status="editing", template=cfg["caption_template"], layout=cfg["layout"], origin="manual",
                    created_at=db.now())
    return clip_out(get_clip(cid))


@app.post("/api/projects/{pid}/review-time")
async def review_time(pid: int, request: Request):
    get_project(pid)
    data = await body(request)
    sec = max(0.0, min(60.0, float(data.get("seconds") or 0)))
    db.run("UPDATE projects SET review_seconds = review_seconds + ? WHERE id=?", (sec, pid))
    return {"ok": True}


@app.post("/api/projects/{pid}/export-accepted")
def export_accepted(pid: int):
    get_project(pid)
    rows = db.q("SELECT * FROM clips WHERE project_id=? AND status='editing' AND (export_file IS NULL OR export_stale=1)",
                (pid,))
    queued = 0
    for c in rows:
        if not _active_job(c["id"], "export"):
            jobs.enqueue("export", project_id=pid, clip_id=c["id"])
            queued += 1
    return {"queued": queued}


def _delete_project(pid: int):
    db.run("DELETE FROM jobs WHERE project_id=?", (pid,))
    db.run("DELETE FROM projects WHERE id=?", (pid,))
    shutil.rmtree(config.PROJECTS_DIR / str(pid), ignore_errors=True)


@app.delete("/api/projects/{pid}")
def delete_project(pid: int):
    p = get_project(pid)
    if p["status"] == "processing":
        fail(409, "Dieses Projekt wird gerade verarbeitet. Bitte warte, bis es fertig ist.")
    _delete_project(pid)
    return {"ok": True}


# ---------------------------------------------------------------- Clips

def _active_job(cid: int, kind: str):
    return db.one("SELECT id FROM jobs WHERE clip_id=? AND kind=? AND status IN ('queued','running')", (cid, kind))


@app.get("/api/clips/{cid}")
def clip_detail(cid: int):
    return clip_out(get_clip(cid), stats.ledger())


@app.patch("/api/clips/{cid}")
async def patch_clip(cid: int, request: Request):
    c = get_clip(cid)
    p = get_project(c["project_id"])
    data = await body(request)
    patch, stale = {}, False
    if "start" in data or "end" in data:
        start = _num(data.get("start", c["start"]), "Start", 0, max(0.0, p["duration"]))
        end = _num(data.get("end", c["end"]), "Ende", 0, max(0.0, p["duration"]) + 0.5)
        if end - start < 1:
            fail(400, "Ein Clip muss mindestens eine Sekunde lang sein.")
        if end - start > 180:
            fail(400, "Ein Clip darf höchstens 3 Minuten lang sein.")
        if abs(start - c["start"]) > 1e-3 or abs(end - c["end"]) > 1e-3:
            patch.update(start=round(start, 2), end=round(end, 2))
            stale = True
    if "user_score" in data:
        patch["user_score"] = None if data["user_score"] in (None, "") else _num(data["user_score"], "Score", 0, 100, True)
    for k in ("title", "hook"):
        if k in data:
            v = str(data[k] or "")[:300]
            if v != (c[k] or ""):
                patch[k] = v
                stale = stale or k == "hook"
    if "hook_enabled" in data and bool(data["hook_enabled"]) != bool(c["hook_enabled"]):
        patch["hook_enabled"] = 1 if data["hook_enabled"] else 0
        stale = True
    if "template" in data and data["template"] != c["template"]:
        if data["template"] not in captions.TEMPLATES:
            fail(400, "Unbekannte Untertitel-Vorlage.")
        patch["template"] = data["template"]
        stale = True
    if "layout" in data and data["layout"] != c["layout"]:
        if data["layout"] not in ("auto", "face", "blur"):
            fail(400, "Unbekanntes Layout.")
        patch["layout"] = data["layout"]
        stale = True
    if "campaign_id" in data:
        cid_new = data["campaign_id"] or None
        if cid_new and not db.one("SELECT id FROM campaigns WHERE id=?", (cid_new,)):
            fail(400, "Kampagne nicht gefunden.")
        patch["campaign_id"] = cid_new
    if "texts" in data and isinstance(data["texts"], dict):
        patch["texts"] = data["texts"]
    if stale and c["export_file"]:
        patch["export_stale"] = 1
    db.update("clips", cid, **patch)
    return clip_out(get_clip(cid), stats.ledger())


@app.post("/api/clips/{cid}/move")
async def move_clip(cid: int, request: Request):
    """Status ändern (Review-Buttons und Drag & Drop in der Pipeline)."""
    c = get_clip(cid)
    data = await body(request)
    target = data.get("status")
    if target not in STATUSES:
        fail(400, "Unbekannter Status.")
    result = {"queued_export": False}
    if target == "done" and (not c["export_file"] or c["export_stale"]):
        if c["is_sample"]:
            fail(409, "Beispiel-Clips haben kein Video und können nicht exportiert werden.")
        db.update("clips", cid, status="editing")
        if not _active_job(cid, "export"):
            jobs.enqueue("export", project_id=c["project_id"], clip_id=cid)
        result["queued_export"] = True
    elif target == "posted":
        if not db.one("SELECT id FROM posts WHERE clip_id=?", (cid,)):
            fail(409, "Trage zuerst ein, wo der Clip gepostet wurde.")
        db.update("clips", cid, status="posted")
    else:
        db.update("clips", cid, status=target)
    result["clip"] = clip_out(get_clip(cid), stats.ledger())
    return result


@app.post("/api/clips/{cid}/export")
def export_clip(cid: int):
    c = get_clip(cid)
    if c["is_sample"]:
        fail(409, "Beispiel-Clips haben kein Video und können nicht exportiert werden.")
    if _active_job(cid, "export"):
        fail(409, "Dieser Clip wird schon exportiert.")
    if c["status"] in ("candidate", "rejected"):
        db.update("clips", cid, status="editing")
    return {"job": jobs.enqueue("export", project_id=c["project_id"], clip_id=cid)}


@app.post("/api/clips/{cid}/texts")
def make_texts(cid: int):
    c = get_clip(cid)
    if c["is_sample"]:
        fail(409, "Für Beispiel-Clips gibt es kein Transkript.")
    if _active_job(cid, "texts"):
        fail(409, "Die Texte werden schon geschrieben.")
    return {"job": jobs.enqueue("texts", project_id=c["project_id"], clip_id=cid)}


@app.get("/api/clips/{cid}/file")
def clip_file(cid: int, download: int = 0):
    c = get_clip(cid)
    if not c["export_file"]:
        fail(404, "Dieser Clip wurde noch nicht exportiert.")
    f = config.project_dir(c["project_id"]) / c["export_file"]
    if not f.exists():
        fail(404, "Die exportierte Datei fehlt.")
    if download:
        safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in (c["title"] or f"clip_{cid}")).strip()[:60]
        return FileResponse(f, media_type="video/mp4", filename=f"{safe or 'clip'}.mp4")
    return FileResponse(f, media_type="video/mp4")


@app.get("/api/clips/{cid}/thumb")
def clip_thumb(cid: int):
    c = get_clip(cid)
    pdir = config.project_dir(c["project_id"])
    f = pdir / "exports" / f"clip_{cid}.jpg"
    if c["export_file"] and not c["export_stale"] and f.exists():
        return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
    return project_thumb(c["project_id"], round(c["start"] + min(2.0, (c["end"] - c["start"]) / 2), 1))


@app.post("/api/clips/{cid}/reveal")
def reveal(cid: int):
    """Öffnet den Ordner mit dem exportierten Clip im Datei-Explorer."""
    c = get_clip(cid)
    if not c["export_file"]:
        fail(404, "Dieser Clip wurde noch nicht exportiert.")
    folder = (config.project_dir(c["project_id"]) / c["export_file"]).parent
    try:
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception:
        pass
    return {"folder": str(folder)}


@app.delete("/api/clips/{cid}")
def delete_clip(cid: int):
    c = get_clip(cid)
    if _active_job(cid, "export"):
        fail(409, "Dieser Clip wird gerade exportiert.")
    if c["export_file"]:
        f = config.project_dir(c["project_id"]) / c["export_file"]
        f.unlink(missing_ok=True)
        f.with_suffix(".jpg").unlink(missing_ok=True)
    db.run("DELETE FROM clips WHERE id=?", (cid,))
    return {"ok": True}


# ---------------------------------------------------------------- Pipeline

@app.get("/api/pipeline")
def pipeline():
    led = stats.ledger()
    cols = {s: [] for s in ("candidate", "editing", "done", "posted")}
    rows = db.q("SELECT c.*, p.title AS project_title FROM clips c JOIN projects p ON p.id=c.project_id "
                "WHERE c.status != 'rejected' ORDER BY COALESCE(c.user_score, c.ai_score) DESC, c.id DESC")
    active = {j["clip_id"]: j for j in db.q("SELECT * FROM jobs WHERE clip_id IS NOT NULL AND status IN ('queued','running')")}
    for r in rows:
        c = clip_out(r, led)
        c["job"] = active.get(r["id"])
        cols[r["status"]].append(c)
    cols["posted"].sort(key=lambda c: max((p["posted_at"] for p in c["posts"]), default=""), reverse=True)
    raw = [project_out(p) for p in db.q("SELECT * FROM projects WHERE status != 'sample' ORDER BY id DESC")]
    return {"raw": raw, **cols}


# ---------------------------------------------------------------- Kampagnen, Posts, Einnahmen

def _campaign_fields(data: dict, partial: bool) -> dict:
    out = {}
    if "name" in data or not partial:
        name = str(data.get("name") or "").strip()
        if not name:
            fail(400, "Die Kampagne braucht einen Namen.")
        out["name"] = name[:120]
    if "platform" in data:
        out["platform"] = str(data["platform"] or "")[:60]
    if "rate_per_1000" in data or not partial:
        out["rate_per_1000"] = _num(data.get("rate_per_1000", 0), "Bezahlung pro 1.000 Views", 0, 1000)
    if "budget" in data:
        out["budget"] = _num(data["budget"] or 0, "Budget", 0, 10_000_000)
    if "rules" in data:
        out["rules"] = str(data["rules"] or "")[:2000]
    if "active" in data:
        out["active"] = 1 if data["active"] else 0
    return out


@app.get("/api/campaigns")
def campaigns():
    return stats.earnings()["campaigns"]


@app.post("/api/campaigns")
async def add_campaign(request: Request):
    f = _campaign_fields(await body(request), partial=False)
    cid = db.insert("campaigns", created_at=db.now(), **f)
    return db.one("SELECT * FROM campaigns WHERE id=?", (cid,))


@app.patch("/api/campaigns/{cid}")
async def patch_campaign(cid: int, request: Request):
    if not db.one("SELECT id FROM campaigns WHERE id=?", (cid,)):
        fail(404, "Kampagne nicht gefunden.")
    db.update("campaigns", cid, **_campaign_fields(await body(request), partial=True))
    return db.one("SELECT * FROM campaigns WHERE id=?", (cid,))


@app.delete("/api/campaigns/{cid}")
def delete_campaign(cid: int):
    db.run("DELETE FROM campaigns WHERE id=?", (cid,))
    return {"ok": True}


def _date(v, default=None) -> str:
    v = str(v or default or db.today())[:10]
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        fail(400, "Ungültiges Datum.")
    if v > db.today():
        fail(400, "Das Datum liegt in der Zukunft.")
    return v


@app.post("/api/posts")
async def add_post(request: Request):
    data = await body(request)
    clip = get_clip(int(data.get("clip_id") or 0))
    platform = str(data.get("platform") or "").strip()
    if not platform:
        fail(400, "Bitte eine Plattform wählen.")
    camp = data.get("campaign_id") or None
    if camp and not db.one("SELECT id FROM campaigns WHERE id=?", (camp,)):
        fail(400, "Kampagne nicht gefunden.")
    views = _num(data.get("views") or 0, "Views", 0, 10_000_000_000, True)
    pid = db.insert("posts", clip_id=clip["id"], campaign_id=camp, platform=platform[:60],
                    url=str(data.get("url") or "").strip()[:500], posted_at=_date(data.get("posted_at")), views=views,
                    views_updated_at=db.now(), is_sample=clip["is_sample"], created_at=db.now())
    if views:
        db.insert("view_log", post_id=pid, day=db.today(), views_delta=views, created_at=db.now())
    if clip["status"] != "posted":
        db.update("clips", clip["id"], status="posted")
    return db.one("SELECT * FROM posts WHERE id=?", (pid,))


@app.patch("/api/posts/{pid}")
async def patch_post(pid: int, request: Request):
    post = db.one("SELECT * FROM posts WHERE id=?", (pid,))
    if not post:
        fail(404, "Post nicht gefunden.")
    data = await body(request)
    patch = {}
    if "views" in data:
        views = _num(data["views"], "Views", 0, 10_000_000_000, True)
        delta = views - (post["views"] or 0)
        if delta:
            db.insert("view_log", post_id=pid, day=db.today(), views_delta=delta, created_at=db.now())
        patch.update(views=views, views_updated_at=db.now())
    if "url" in data:
        patch["url"] = str(data["url"] or "").strip()[:500]
    if "platform" in data and str(data["platform"]).strip():
        patch["platform"] = str(data["platform"]).strip()[:60]
    if "campaign_id" in data:
        camp = data["campaign_id"] or None
        if camp and not db.one("SELECT id FROM campaigns WHERE id=?", (camp,)):
            fail(400, "Kampagne nicht gefunden.")
        patch["campaign_id"] = camp
    if "posted_at" in data:
        patch["posted_at"] = _date(data["posted_at"])
    db.update("posts", pid, **patch)
    return db.one("SELECT * FROM posts WHERE id=?", (pid,))


@app.delete("/api/posts/{pid}")
def delete_post(pid: int):
    post = db.one("SELECT * FROM posts WHERE id=?", (pid,))
    if not post:
        fail(404, "Post nicht gefunden.")
    db.run("DELETE FROM posts WHERE id=?", (pid,))
    if not db.one("SELECT id FROM posts WHERE clip_id=?", (post["clip_id"],)):
        clip = get_clip(post["clip_id"])
        if clip["status"] == "posted":
            db.update("clips", clip["id"], status="done" if clip["export_file"] else "editing")
    return {"ok": True}


@app.get("/api/earnings")
def earnings():
    return stats.earnings()


@app.get("/api/dashboard")
def dashboard():
    return stats.dashboard()


# ---------------------------------------------------------------- Beispieldaten

@app.post("/api/sample")
def sample_load():
    sample.load()
    return {"ok": True}


@app.delete("/api/sample")
def sample_clear():
    sample.clear()
    return {"ok": True}


# ---------------------------------------------------------------- Oberfläche

class NoCacheStatic(StaticFiles):
    """Statische Dateien ohne Browser-Cache, damit nach einem Update immer die neue Oberfläche lädt."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


@app.get("/")
def index():
    return FileResponse(config.WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", NoCacheStatic(directory=config.WEB_DIR), name="static")
