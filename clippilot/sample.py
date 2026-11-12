"""Beispieldaten zum Ausprobieren. Alles ist mit is_sample=1 markiert und mit einem Klick löschbar."""
import random
from datetime import date, datetime, timedelta

from . import db


def exists() -> bool:
    return any(db.one(f"SELECT 1 AS x FROM {t} WHERE is_sample=1 LIMIT 1") for t in
               ("projects", "clips", "campaigns", "posts"))


def clear():
    # Reihenfolge wichtig: Posts und View-Einträge hängen an Clips, Clips an Projekten.
    db.run("DELETE FROM posts WHERE is_sample=1")
    db.run("DELETE FROM clips WHERE is_sample=1")
    db.run("DELETE FROM projects WHERE is_sample=1")
    db.run("DELETE FROM campaigns WHERE is_sample=1")


def load():
    if exists():
        return
    rnd = random.Random(7)
    today = date.today()
    now = db.now()
    c1 = db.insert("campaigns", name="Beispiel: NovaPlays Highlights", platform="TikTok", rate_per_1000=1.2,
                   budget=600, rules="Pflicht-Hashtag #novaplays, kein Fluchen, Länge 20–60 s", active=1,
                   is_sample=1, created_at=now)
    c2 = db.insert("campaigns", name="Beispiel: Podcast-Clips", platform="YouTube Shorts", rate_per_1000=0.8,
                   budget=1500, rules="Kanal im Text erwähnen, #shorts", active=1, is_sample=1, created_at=now)
    pid = db.insert("projects", title="Beispiel-Stream (ohne Video)", source_kind="sample", status="sample",
                    duration=7200, language="de", is_sample=1, created_at=now)
    titles = ["1v4 Clutch in letzter Sekunde", "Chat rastet komplett aus", "Die teuerste Fehlentscheidung",
              "Warum niemand Clips postet", "Katze beendet das Match", "Der Tipp, der alles geändert hat",
              "Zwölf Euro im ersten Monat", "Das sagt dir keiner über Shorts", "Rage Quit des Jahres",
              "So findest du den Hook", "Drei Tage Arbeit, 40 Views", "Der Moment, als es klick gemacht hat",
              "Fünf Clips am Tag", "Stream-Fail mit Ansage"]
    platforms = ["TikTok", "YouTube Shorts", "Instagram Reels"]
    for k, title in enumerate(titles):
        day = today - timedelta(days=12 - k if k < 12 else 0)
        cid = db.insert("clips", project_id=pid, idx=k + 1, title=title, start=k * 300.0, end=k * 300.0 + 38,
                        ai_start=k * 300.0, ai_end=k * 300.0 + 38, ai_score=rnd.randint(62, 94), reason_tag="hook",
                        reason="Beispiel-Clip", hook=title, status="posted", origin="ai", is_sample=1,
                        created_at=datetime.combine(day, datetime.min.time()).isoformat())
        camp = c1 if k % 3 else c2
        plat = platforms[k % 3]
        post = db.insert("posts", clip_id=cid, campaign_id=camp, platform=plat,
                         url=f"https://example.com/beispiel/{k + 1}", posted_at=day.isoformat(), views=0,
                         is_sample=1, created_at=now, views_updated_at=now)
        total = 0
        d, age = day, 0
        base = rnd.choice([3000, 6000, 9000, 15000, 42000])
        while d <= today:
            delta = int(base * (0.55 ** age) * rnd.uniform(0.7, 1.3))
            if delta > 0:
                db.insert("view_log", post_id=post, day=d.isoformat(), views_delta=delta, created_at=now)
                total += delta
            d += timedelta(days=1)
            age += 1
        db.update("posts", post, views=total)
