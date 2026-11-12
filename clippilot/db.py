"""SQLite-Datenbank: Projekte, Clips, Kampagnen, Posts, Views, Jobs."""
import json
import sqlite3
import threading
from datetime import datetime

from . import config

_local = threading.local()
_write_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  source_kind TEXT NOT NULL DEFAULT 'upload',
  source_url TEXT,
  filename TEXT,
  preview_file TEXT,
  duration REAL DEFAULT 0,
  width INTEGER DEFAULT 0,
  height INTEGER DEFAULT 0,
  fps REAL DEFAULT 0,
  language TEXT,
  status TEXT NOT NULL DEFAULT 'imported',
  error TEXT,
  analysis_engine TEXT,
  analysis_note TEXT,
  review_seconds REAL DEFAULT 0,
  is_sample INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  idx INTEGER DEFAULT 0,
  title TEXT,
  start REAL NOT NULL,
  end REAL NOT NULL,
  ai_start REAL,
  ai_end REAL,
  ai_score INTEGER DEFAULT 0,
  user_score INTEGER,
  reason_tag TEXT,
  reason TEXT,
  hook TEXT,
  hook_enabled INTEGER DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'candidate',
  template TEXT,
  layout TEXT,
  focus_x REAL,
  export_file TEXT,
  export_seconds REAL,
  exported_at TEXT,
  export_stale INTEGER DEFAULT 0,
  texts TEXT,
  texts_engine TEXT,
  origin TEXT DEFAULT 'ai',
  campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
  is_sample INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS campaigns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  platform TEXT,
  rate_per_1000 REAL DEFAULT 0,
  budget REAL DEFAULT 0,
  rules TEXT,
  active INTEGER DEFAULT 1,
  is_sample INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
  platform TEXT NOT NULL,
  url TEXT,
  posted_at TEXT NOT NULL,
  views INTEGER DEFAULT 0,
  views_updated_at TEXT,
  is_sample INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS view_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  day TEXT NOT NULL,
  views_delta INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  project_id INTEGER,
  clip_id INTEGER,
  payload TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  progress REAL DEFAULT 0,
  message TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  seconds REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS idx_clips_project ON clips(project_id);
CREATE INDEX IF NOT EXISTS idx_posts_clip ON posts(clip_id);
CREATE INDEX IF NOT EXISTS idx_log_post ON view_log(post_id);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        config.ensure_dirs()
        c = sqlite3.connect(config.DB_FILE, timeout=30, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        _local.conn = c
    return c


def init():
    with _write_lock:
        conn().executescript(SCHEMA)
        conn().commit()


def q(sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn().execute(sql, params).fetchall()]


def one(sql: str, params=()) -> dict | None:
    r = conn().execute(sql, params).fetchone()
    return dict(r) if r else None


def run(sql: str, params=()) -> int:
    with _write_lock:
        cur = conn().execute(sql, params)
        conn().commit()
        return cur.lastrowid


def insert(table: str, **fields) -> int:
    keys = list(fields)
    sql = f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})"
    return run(sql, [_enc(fields[k]) for k in keys])


def update(table: str, row_id: int, **fields):
    if not fields:
        return
    sets = ",".join(f"{k}=?" for k in fields)
    run(f"UPDATE {table} SET {sets} WHERE id=?", [_enc(v) for v in fields.values()] + [row_id])


def _enc(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return int(v)
    return v


def meta_get(key: str, default=None):
    r = one("SELECT value FROM meta WHERE key=?", (key,))
    return json.loads(r["value"]) if r else default


def meta_set(key: str, value):
    run("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False)))
