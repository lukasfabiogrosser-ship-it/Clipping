"""Pfade und Einstellungen. Einstellungen (inkl. API-Key) liegen nur in data/config.json."""
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("CLIPPILOT_DATA", ROOT / "data")).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
CONFIG_FILE = DATA_DIR / "config.json"
DB_FILE = DATA_DIR / "clippilot.db"
WEB_DIR = PKG / "web"
FONT_DIR = PKG / "assets" / "fonts"
FACE_MODEL = PKG / "assets" / "models" / "face_detection_yunet_2023mar.onnx"

HOST = "127.0.0.1"
PORT = int(os.environ.get("CLIPPILOT_PORT", "8756"))

AI_MODELS = [
    {"id": "claude-opus-5-5", "label": "Claude Opus 5.5 – beste Qualität (empfohlen)"},
    {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5 – schneller und günstiger"},
    {"id": "claude-haiku-5-5", "label": "Claude Haiku 5.5 – am günstigsten"},
]
WHISPER_MODELS = [
    {"id": "tiny", "label": "Tiny – sehr schnell, ungenau"},
    {"id": "base", "label": "Base – schnell"},
    {"id": "small", "label": "Small – guter Mittelweg (empfohlen ohne Grafikkarte)"},
    {"id": "medium", "label": "Medium – genauer, langsamer"},
    {"id": "large-v3", "label": "Large v3 – am genauesten (Grafikkarte empfohlen)"},
]

DEFAULTS = {
    "anthropic_api_key": "",
    "ai_model": "claude-opus-5-5",
    "whisper_model": "small",
    "language": "auto",            # auto | de | en
    "clip_min_s": 20,
    "clip_max_s": 60,
    "num_suggestions": 10,
    "caption_template": "pop",
    "layout": "auto",              # auto | face | blur
    "hook_seconds": 2.5,
    "goal_clips_per_day": 5,
    "goal_month_eur": 1500,
    "manual_minutes_per_clip": 45,
}

_lock = threading.Lock()


def ensure_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    s = dict(DEFAULTS)
    try:
        s.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return s


def save_settings(patch: dict) -> dict:
    with _lock:
        s = load_settings()
        for k, v in patch.items():
            if k in DEFAULTS:
                s[k] = v
        ensure_dirs()
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CONFIG_FILE)
        return s


def public_settings() -> dict:
    """Einstellungen fürs Frontend – der API-Key verlässt das Backend nie im Klartext."""
    s = load_settings()
    key = s.pop("anthropic_api_key", "") or ""
    s["has_api_key"] = bool(key)
    s["api_key_hint"] = ("…" + key[-4:]) if len(key) >= 8 else ""
    return s


def project_dir(pid: int) -> Path:
    d = PROJECTS_DIR / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    return d
