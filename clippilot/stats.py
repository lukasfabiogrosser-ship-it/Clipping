"""Auswertung: Einnahmen, Ziele, Hochrechnung, Zeitersparnis, Serie, Erfolge, Ampel."""
import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta

from . import config, db


def _d(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def ledger() -> dict:
    """Einnahmen aus den eingetragenen View-Zuwächsen, pro Kampagne begrenzt auf ihr Budget."""
    camps = {c["id"]: c for c in db.q("SELECT * FROM campaigns")}
    rows = db.q("SELECT l.id, l.post_id, l.day, l.views_delta, p.campaign_id, p.clip_id FROM view_log l "
                "JOIN posts p ON p.id=l.post_id ORDER BY l.day, l.id")
    spent = defaultdict(float)
    by_day, views_day = defaultdict(float), defaultdict(int)
    by_post, by_camp, by_clip = defaultdict(float), defaultdict(float), defaultdict(float)
    for r in rows:
        views_day[r["day"]] += r["views_delta"]
        c = camps.get(r["campaign_id"])
        if not c:
            continue
        raw = r["views_delta"] * (c["rate_per_1000"] or 0) / 1000.0
        if (c["budget"] or 0) > 0:
            earn = min(raw, c["budget"] - spent[c["id"]]) if raw > 0 else max(raw, -spent[c["id"]])
        else:
            earn = raw
        spent[c["id"]] += earn
        by_day[r["day"]] += earn
        by_post[r["post_id"]] += earn
        by_camp[c["id"]] += earn
        by_clip[r["clip_id"]] += earn
    return {"by_day": by_day, "views_day": views_day, "by_post": by_post, "by_camp": by_camp, "by_clip": by_clip,
            "total": sum(by_day.values()), "camps": camps}


def _posted_days() -> dict:
    """Tag -> Anzahl verschiedener Clips, die an dem Tag zum ersten Mal gepostet wurden."""
    first = {}
    for r in db.q("SELECT clip_id, MIN(posted_at) AS d FROM posts GROUP BY clip_id"):
        first[r["clip_id"]] = r["d"][:10]
    days = defaultdict(int)
    for d in first.values():
        days[d] += 1
    return days


def _streak(days: dict, today: date) -> tuple[int, int]:
    have = {_d(k) for k, v in days.items() if v > 0}
    cur, d = 0, today
    if d not in have:
        d -= timedelta(days=1)          # heute zählt erst, wenn gepostet wurde – die Serie reißt aber noch nicht
    while d in have:
        cur += 1
        d -= timedelta(days=1)
    best, run, prev = 0, 0, None
    for d in sorted(have):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best, prev = max(best, run), d
    return cur, best


def time_saved(cfg: dict) -> dict:
    """Vergleich: so lange brauchst du von Hand (deine Angabe) gegen gemessene Zeit in der App."""
    row = db.one("SELECT COUNT(*) AS n FROM clips WHERE export_file IS NOT NULL AND is_sample=0")
    n = row["n"]
    manual = float(cfg["manual_minutes_per_clip"])
    if n == 0:
        return {"clips": 0, "manual_min": manual, "app_min": None, "saved_min": None, "machine_min": None,
                "review_min": None}
    pids = [r["project_id"] for r in db.q("SELECT DISTINCT project_id FROM clips WHERE export_file IS NOT NULL "
                                          "AND is_sample=0")]
    marks = ",".join("?" * len(pids))
    machine = db.one(f"SELECT COALESCE(SUM(seconds),0) AS s FROM jobs WHERE status='done' AND project_id IN ({marks})",
                     pids)["s"]
    review = db.one(f"SELECT COALESCE(SUM(review_seconds),0) AS s FROM projects WHERE id IN ({marks})", pids)["s"]
    machine_min = machine / 60 / n
    review_min = review / 60 / n
    app = machine_min + review_min
    return {"clips": n, "manual_min": manual, "app_min": round(app, 1), "saved_min": round(manual - app, 1),
            "machine_min": round(machine_min, 1), "review_min": round(review_min, 1)}


ACHIEVEMENTS = [
    ("export_1", "Erster Schnitt", "Exportiere deinen ersten Clip", "exports", 1),
    ("export_10", "Schnittmeister", "Exportiere 10 Clips", "exports", 10),
    ("export_50", "Fließband", "Exportiere 50 Clips", "exports", 50),
    ("post_1", "On Air", "Poste deinen ersten Clip", "posted", 1),
    ("post_25", "Dauersender", "Poste 25 Clips", "posted", 25),
    ("views_10k", "Erste Welle", "Erreiche 10.000 Views", "views", 10_000),
    ("views_100k", "Reichweite", "Erreiche 100.000 Views", "views", 100_000),
    ("views_1m", "Millionenpublikum", "Erreiche 1.000.000 Views", "views", 1_000_000),
    ("eur_1", "Erster Euro", "Verdiene deinen ersten Euro", "earned", 1),
    ("eur_100", "Dreistellig", "Verdiene 100 €", "earned", 100),
    ("eur_1000", "Vierstellig", "Verdiene 1.000 €", "earned", 1000),
    ("quest_1", "Tagesquest", "Schaffe ein Tagesziel", "quests", 1),
    ("streak_3", "Dranbleiber", "Poste 3 Tage in Folge", "best_streak", 3),
    ("streak_7", "Wochenserie", "Poste 7 Tage in Folge", "best_streak", 7),
    ("streak_30", "Monatsserie", "Poste 30 Tage in Folge", "best_streak", 30),
]


def dashboard() -> dict:
    cfg = config.load_settings()
    today = date.today()
    tkey = today.isoformat()
    led = ledger()
    days = _posted_days()
    goal_day, goal_month = int(cfg["goal_clips_per_day"]), float(cfg["goal_month_eur"])

    series = []
    for k in range(29, -1, -1):
        d = (today - timedelta(days=k)).isoformat()
        series.append({"day": d, "earnings": round(led["by_day"].get(d, 0.0), 2),
                       "views": int(led["views_day"].get(d, 0)), "clips": days.get(d, 0)})
    last7 = series[-7:]
    prev7 = series[-14:-7]
    month_prefix = tkey[:7]
    month_earn = sum(v for d, v in led["by_day"].items() if d.startswith(month_prefix))
    dim = calendar.monthrange(today.year, today.month)[1]
    # Soll-Stand: anteilig ab dem Tag, an dem du in diesem Monat angefangen hast (nicht ab dem 1.)
    first_log = min(led["views_day"]) if led["views_day"] else None
    start_day = _d(first_log).day if first_log and first_log.startswith(month_prefix) else 1
    soll = goal_month * (today.day - start_day + 1) / dim if goal_month else 0

    # Hochrechnung aus dem Schnitt der letzten 7 Tage (bei weniger Verlauf: seit dem ersten Eintrag)
    log_days = sorted(led["views_day"])
    proj = None
    if log_days:
        span = min(7, max(1, (today - _d(log_days[0])).days + 1))
        avg = sum(s["earnings"] for s in series[-span:]) / span
        proj = {"basis_days": span, "per_day": round(avg, 2), "week": round(avg * 7, 2),
                "month": round(avg * 30, 2), "year": round(avg * 365, 2)}

    cur_streak, best_streak = _streak(days, today)
    quests_done = sum(1 for v in days.values() if goal_day > 0 and v >= goal_day)
    total_views = db.one("SELECT COALESCE(SUM(views),0) AS v FROM posts")["v"]
    counts = {r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) AS n FROM clips GROUP BY status")}
    exports = db.one("SELECT COUNT(*) AS n FROM clips WHERE export_file IS NOT NULL OR (is_sample=1 AND status='posted')")["n"]
    posted = len({r["clip_id"] for r in db.q("SELECT DISTINCT clip_id FROM posts")})
    vals = {"exports": exports, "posted": posted, "views": total_views, "earned": led["total"],
            "quests": quests_done, "best_streak": best_streak}
    achievements = [{"id": a, "title": t, "desc": d, "value": min(vals[k], target), "target": target,
                     "done": vals[k] >= target} for a, t, d, k, target in ACHIEVEMENTS]

    # Was heute ansteht
    agenda = []
    n_projects = db.one("SELECT COUNT(*) AS n FROM projects WHERE is_sample=0")["n"]
    if n_projects == 0:
        agenda.append({"kind": "import", "text": "Importiere dein erstes Video", "count": None, "link": "#/projekte"})
    proc = db.one("SELECT COUNT(*) AS n FROM projects WHERE status='processing'")["n"]
    if proc:
        agenda.append({"kind": "busy", "text": "Videos werden gerade verarbeitet", "count": proc, "link": "#/projekte"})
    cand = db.one("SELECT project_id, COUNT(*) AS n FROM clips WHERE status='candidate' AND is_sample=0 "
                  "GROUP BY project_id ORDER BY n DESC")
    n_cand = db.one("SELECT COUNT(*) AS n FROM clips WHERE status='candidate' AND is_sample=0")["n"]
    if n_cand:
        agenda.append({"kind": "review", "text": "Vorschläge prüfen", "count": n_cand,
                       "link": f"#/projekt/{cand['project_id']}"})
    n_edit = db.one("SELECT COUNT(*) AS n FROM clips WHERE status='editing' AND is_sample=0")["n"]
    if n_edit:
        agenda.append({"kind": "export", "text": "Angenommene Clips exportieren", "count": n_edit, "link": "#/pipeline"})
    n_done = db.one("SELECT COUNT(*) AS n FROM clips WHERE status='done' AND is_sample=0")["n"]
    if n_done:
        agenda.append({"kind": "post", "text": "Fertige Clips posten", "count": n_done, "link": "#/pipeline"})
    stale_cut = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
    recent_cut = (today - timedelta(days=30)).isoformat()
    n_stale = db.one("SELECT COUNT(*) AS n FROM posts WHERE COALESCE(views_updated_at, created_at) < ? AND posted_at >= ?",
                     (stale_cut, recent_cut))["n"]
    if n_stale:
        agenda.append({"kind": "views", "text": "Views aktualisieren", "count": n_stale, "link": "#/kampagnen"})
    done_today = days.get(tkey, 0)
    if goal_day and done_today < goal_day:
        agenda.append({"kind": "quest", "text": f"Noch {goal_day - done_today} "
                       f"{'Clip' if goal_day - done_today == 1 else 'Clips'} bis zum Tagesziel", "count": None,
                       "link": "#/pipeline"})

    # Ampel
    warnings = []
    camp_rows = []
    for c in led["camps"].values():
        earned = led["by_camp"].get(c["id"], 0.0)
        used = earned / c["budget"] if (c["budget"] or 0) > 0 else None
        camp_rows.append({"id": c["id"], "name": c["name"], "earned": round(earned, 2), "budget": c["budget"],
                          "used": used, "active": c["active"]})
        if c["active"] and used is not None and used >= 0.85:
            warnings.append({"level": "red" if used >= 1 else "yellow",
                             "text": f"Budget von „{c['name']}“ {'ist aufgebraucht' if used >= 1 else f'zu {int(used * 100)} % verbraucht'}"})
    has_history = bool(log_days)
    if goal_month and has_history and (today - _d(log_days[0])).days >= 2:
        pace = month_earn / soll if soll else 1
        if pace < 0.6:
            warnings.append({"level": "red", "text": f"Monatsziel stark gefährdet ({_eur(soll - month_earn)} hinter Plan)"})
        elif pace < 0.9:
            warnings.append({"level": "yellow", "text": f"Einnahmen unter Plan ({_eur(soll - month_earn)} hinter Plan)"})
    if n_stale:
        warnings.append({"level": "yellow", "text": f"{n_stale} {'Post braucht' if n_stale == 1 else 'Posts brauchen'} frische View-Zahlen"})
    if not has_history and posted == 0:
        status = {"level": "start", "title": "Bereit", "text": "Noch keine Posts – leg los mit deinem ersten Video"}
    elif any(w["level"] == "red" for w in warnings):
        status = {"level": "red", "title": "Handlungsbedarf", "text": warnings[0]["text"]}
    elif warnings:
        status = {"level": "yellow", "title": "Achtung", "text": warnings[0]["text"]}
    else:
        status = {"level": "green", "title": "Läuft gut", "text": "Alles im grünen Bereich"}
    warnings.sort(key=lambda w: 0 if w["level"] == "red" else 1)

    return {
        "today": {"date": tkey, "clips": done_today, "views": int(led["views_day"].get(tkey, 0)),
                  "earnings": round(led["by_day"].get(tkey, 0.0), 2)},
        "week": {"earnings": round(sum(s["earnings"] for s in last7), 2), "views": sum(s["views"] for s in last7),
                 "clips": sum(s["clips"] for s in last7),
                 "prev_earnings": round(sum(s["earnings"] for s in prev7), 2),
                 "prev_views": sum(s["views"] for s in prev7), "prev_clips": sum(s["clips"] for s in prev7)},
        "month": {"earnings": round(month_earn, 2), "goal": goal_month, "soll": round(soll, 2),
                  "day": today.day, "days": dim, "name": _MONTHS[today.month - 1], "start_day": start_day},
        "projection": proj,
        "time_saved": time_saved(cfg),
        "quest": {"target": goal_day, "done": done_today},
        "streak": {"current": cur_streak, "best": best_streak, "today_done": done_today > 0},
        "achievements": achievements,
        "agenda": agenda, "warnings": warnings, "status": status, "series": series,
        "counts": counts, "campaigns": camp_rows,
        "totals": {"views": total_views, "earned": round(led["total"], 2), "posted": posted, "exports": exports},
    }


_MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
           "November", "Dezember"]


def _eur(v: float) -> str:
    return f"{v:,.0f} €".replace(",", ".")


def hud() -> dict:
    """Die vier Zahlen für das Mini-Fenster."""
    cfg = config.load_settings()
    tkey = date.today().isoformat()
    led = ledger()
    days = _posted_days()
    return {"clips": days.get(tkey, 0), "views": int(led["views_day"].get(tkey, 0)),
            "earnings": round(led["by_day"].get(tkey, 0.0), 2), "goal": int(cfg["goal_clips_per_day"])}


def earnings() -> dict:
    """Einnahmen je Kampagne, Clip, Tag und Monat."""
    led = ledger()
    camps = []
    for c in led["camps"].values():
        posts = db.one("SELECT COUNT(*) AS n, COALESCE(SUM(views),0) AS v FROM posts WHERE campaign_id=?", (c["id"],))
        earned = led["by_camp"].get(c["id"], 0.0)
        camps.append({**c, "earned": round(earned, 2), "posts": posts["n"], "views": posts["v"],
                      "used": (earned / c["budget"]) if (c["budget"] or 0) > 0 else None})
    camps.sort(key=lambda c: (-c["active"], -c["earned"]))
    posts = db.q("SELECT p.*, c.title AS clip_title, c.project_id, k.name AS campaign_name, k.rate_per_1000 "
                 "FROM posts p JOIN clips c ON c.id=p.clip_id LEFT JOIN campaigns k ON k.id=p.campaign_id "
                 "ORDER BY p.posted_at DESC, p.id DESC")
    for p in posts:
        p["earned"] = round(led["by_post"].get(p["id"], 0.0), 2)
    months = defaultdict(float)
    for d, v in led["by_day"].items():
        months[d[:7]] += v
    return {"campaigns": camps, "posts": posts,
            "days": [{"day": d, "earnings": round(v, 2), "views": int(led["views_day"].get(d, 0))}
                     for d, v in sorted(led["by_day"].items(), reverse=True)][:60],
            "months": [{"month": m, "earnings": round(v, 2)} for m, v in sorted(months.items(), reverse=True)],
            "total": round(led["total"], 2)}
