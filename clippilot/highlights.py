"""Highlight-Finder: schlägt die besten Clip-Momente vor.

Mit Anthropic-API-Key bewertet Claude das Transkript. Ohne Key (oder wenn die KI nicht erreichbar ist)
läuft eine einfachere lokale Analyse aus Stichwörtern, Satzbau und Lautstärke.
"""
import re
import statistics

from . import ai
from .transcribe import sentences as to_sentences

TAGS = {
    "hook": "Starker Hook",
    "funny": "Lustige Pointe",
    "controversial": "Kontroverse Aussage",
    "emotional": "Emotionale Stelle",
    "story": "Story mit Auflösung",
    "surprise": "Überraschende Zahl",
    "insight": "Wertvoller Tipp",
    "reaction": "Laute Reaktion",
}

LEX = {
    "opener": ["ich sage euch", "ich sag euch", "wisst ihr", "weißt du", "stell dir vor", "stellt euch vor",
               "das verrückte", "niemand", "keiner", "der wichtigste", "die wahrheit", "ganz ehrlich", "warum",
               "jetzt aber", "hör zu", "pass auf", "here is", "here's", "nobody", "no one", "the truth",
               "imagine", "what if", "listen", "stop", "why", "the secret", "let me tell you", "you won't believe"],
    "funny": ["gelacht", "lachen", "lustig", "witz", "haha", "katze", "peinlich", "ausgerechnet", "explodier",
              "laughed", "laughing", "funny", "joke", "hilarious", "awkward", "exploding", "exploded"],
    "controversial": ["nicht hören wollen", "verschwenden", "fehler", "falsch", "lüge", "lügen", "betrug", "unpopulär",
                      "niemals", "nie wieder", "schlimmste", "überbewertet", "hass", "skandal", "verboten",
                      "prozent aller", "die meisten", "does not care", "doesn't care", "nobody tells", "mistake",
                      "wrong", "lie", "scam", "overrated", "never", "worst", "unpopular", "hate", "most people"],
    "emotional": ["aufgehört", "aufgeben", "angst", "geweint", "traurig", "stolz", "liebe", "verloren", "grund, warum",
                  "ehrlich", "hart", "schwer", "quit", "gave up", "afraid", "cried", "proud", "love", "lost",
                  "honest", "hard", "struggle"],
    "story": ["geschichte", "letztes jahr", "eines tages", "damals", "früher", "und dann", "aber dann", "plötzlich",
              "story", "last year", "one day", "back then", "i once", "and then", "but then", "suddenly"],
    "insight": ["tipp", "trick", "faustregel", "regel nummer", "geheimnis", "entscheiden", "unterschied", "so geht", "fang ", "mach ",
                "lerne", "gelernt", "tip", "rule", "secret", "the difference", "how to", "start ", "learn",
                "lesson", "the best"],
    "boiler": ["willkommen", "abonnier", "bewertung", "bis bald", "nächste woche", "nächste folge", "in der beschreibung",
               "das war es für heute", "macht es gut", "zur organisation", "welcome", "subscribe", "thanks for listening",
               "thanks for watching", "see you next", "link in the description", "before we start"],
    "number": ["prozent", "tausend", "million", "milliard", "euro", "dollar", "percent", "thousand", "billion"],
}
NUMWORDS = re.compile(r"\b(null|eins|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf|zwanzig|dreißig|vierzig|"
                      r"fünfzig|sechzig|siebzig|achtzig|neunzig|hundert|two|three|four|five|six|seven|eight|nine|ten|"
                      r"twenty|thirty|forty|fifty|hundred)\w*", re.I)


def _hits(text: str, key: str) -> int:
    t = text.lower()
    return sum(1 for w in LEX[key] if w in t)


def _fmt(t: float) -> str:
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}"


def _zscores(loud: list[float]) -> list[float]:
    if len(loud) < 3:
        return [0.0] * len(loud)
    vals = [x for x in loud if x > -70] or loud       # Stille nicht mitzählen
    mean = statistics.fmean(vals)
    sd = statistics.pstdev(vals) or 1.0
    return [(x - mean) / sd for x in loud]


def _sentence_feats(s: dict) -> dict:
    t = s["text"].replace("%", " prozent ")
    n_words = len(t.split())
    numbers = len(re.findall(r"\d[\d.,]*", t)) + len(NUMWORDS.findall(t)) + _hits(t, "number")
    return {
        "q": t.rstrip("\"'”) ").endswith("?"), "excl": "!" in t, "n": n_words, "numbers": numbers,
        **{k: _hits(t, k) for k in ("opener", "funny", "controversial", "emotional", "story", "insight", "boiler")},
    }


def _key_sentence(sents: list[dict], feats: list[dict]) -> int:
    """Der Satz, der am ehesten als Aufhänger taugt (kurz, mit Zahl, Frage oder starker Aussage)."""
    best, best_score = 0, -1e9
    for k, f in enumerate(feats):
        sc = (f["controversial"] * 4 + f["funny"] * 3 + f["insight"] * 3 + f["opener"] * 2 + min(f["numbers"], 1) * 3
              + (2 if f["q"] else 0) + (2 if f["excl"] else 0) - f["boiler"] * 6
              - max(0, f["n"] - 10) * 0.8 - (4 if f["n"] < 4 else 0) - k * 0.4)
        if sc > best_score:
            best, best_score = k, sc
    return best


def _shorten(text: str, max_words: int = 9) -> str:
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip().rstrip(",;:")
    return " ".join(words[:max_words]).rstrip(",;:.") + "…"


def _score_window(sents, feats, z, i, j, target, mx) -> dict:
    start, end = sents[i]["start"], sents[j]["end"]
    dur = max(0.1, end - start)
    fw = feats[i: j + 1]
    head = fw[:2]
    parts = {
        "hook": (12 if any(f["opener"] for f in head) else 0) + (8 if any(f["q"] for f in head) else 0)
                + (6 if any(f["numbers"] for f in head) else 0),
        "funny": min(18, 9 * sum(f["funny"] for f in fw)),
        "controversial": min(18, 8 * sum(f["controversial"] for f in fw)),
        "emotional": min(14, 5 * sum(f["emotional"] for f in fw)),
        "story": min(14, 7 * sum(f["story"] for f in fw)),
        "insight": min(14, 7 * sum(f["insight"] for f in fw)),
        "surprise": min(9, 3 * sum(f["numbers"] for f in fw)),
    }
    zw = z[int(start): max(int(start) + 1, int(end))] or [0.0]
    zmean, zpeak = statistics.fmean(zw), max(zw)
    parts["reaction"] = max(-6.0, min(12.0, zmean * 8)) + (5 if zpeak > 1.5 else 0)
    # Der stärkste Grund zählt voll, weitere Gründe nur anteilig – sonst gewinnt immer der längste Ausschnitt.
    cats = sorted((v for k, v in parts.items() if k not in ("hook", "reaction")), reverse=True)
    score = 28 + 0.8 * parts["hook"] + cats[0] + 0.5 * cats[1] + 0.2 * sum(cats[2:]) + parts["reaction"]
    last = fw[-1]
    if last["n"] <= 9 or last["excl"]:
        score += 4
    # Saubere Grenzen: beginnt nach einer Pause, endet vor einer Pause
    if i == 0 or sents[i]["start"] - sents[i - 1]["end"] >= 0.9:
        score += 4
    if j == len(sents) - 1 or sents[j + 1]["start"] - sents[j]["end"] >= 0.9:
        score += 4
    bland = sum(1 for f in fw if not (f["opener"] or f["funny"] or f["controversial"] or f["emotional"]
                                      or f["story"] or f["insight"] or f["numbers"] or f["q"] or f["excl"]))
    score -= 12 * bland / len(fw)
    score -= 14 * sum(f["boiler"] for f in fw)
    if dur > target:
        score -= 6 * (dur - target) / max(1.0, mx - target)
    words = sum(f["n"] for f in fw)
    if words / dur < 1.6:
        score -= 8
    ranked = dict(parts, hook=0.8 * parts["hook"])
    tag = max(ranked, key=lambda k: ranked[k])
    if ranked[tag] <= 0:
        tag = "hook"
    peak_t = int(start) + zw.index(zpeak)
    return {"i": i, "j": j, "score": int(max(5, min(97, round(score)))), "tag": tag,
            "loud": zpeak > 1.5, "peak_t": peak_t}


def find_local(transcript: dict, loud: list[float], duration: float, cfg: dict) -> list[dict]:
    sents = to_sentences(transcript.get("words", []))
    if not sents:
        return []
    feats = [_sentence_feats(s) for s in sents]
    z = _zscores(loud)
    mn, mx, count = float(cfg["clip_min_s"]), float(cfg["clip_max_s"]), int(cfg["num_suggestions"])
    target = (mn + mx) / 2
    windows = []
    speech = sents[-1]["end"] - sents[0]["start"]
    if speech <= mn * 1.1:
        windows.append(_score_window(sents, feats, z, 0, len(sents) - 1, target, mx))
    else:
        for i in range(len(sents)):
            for j in range(i, len(sents)):
                dur = sents[j]["end"] - sents[i]["start"]
                if dur > mx:
                    break
                if dur >= mn * 0.85:
                    windows.append(_score_window(sents, feats, z, i, j, target, mx))
    windows.sort(key=lambda w: (-w["score"], w["i"]))
    picked = []
    for w in windows:
        a0, a1 = sents[w["i"]]["start"], sents[w["j"]]["end"]
        clash = False
        for p in picked:
            b0, b1 = sents[p["i"]]["start"], sents[p["j"]]["end"]
            overlap = min(a1, b1) - max(a0, b0)
            if overlap > 0.2 * min(a1 - a0, b1 - b0):
                clash = True
                break
        if not clash:
            picked.append(w)
        if len(picked) >= count:
            break
    out = []
    for w in picked:
        ws, wf = sents[w["i"]: w["j"] + 1], feats[w["i"]: w["j"] + 1]
        key = ws[_key_sentence(ws, wf)]["text"]
        proof, tag = key, w["tag"]            # der Satz, der den Grund am besten belegt
        if tag in ("funny", "controversial", "emotional", "story", "insight"):
            top = max(f[tag] for f in wf)
            cands = [k for k, f in enumerate(wf) if f[tag] == top]
            proof = ws[cands[-1] if tag == "funny" else cands[0]]["text"]
        elif tag == "surprise":
            proof = ws[max(range(len(wf)), key=lambda k: wf[k]["numbers"])]["text"]
        reason = f"Schlüsselsatz: „{_shorten(proof, 12)}“"
        if w["loud"] and w["tag"] != "reaction":
            reason += f" Dazu eine laute Stelle bei {_fmt(w['peak_t'])}."
        out.append(_make(sents, w["i"], w["j"], duration, w["score"], w["tag"], reason,
                         _shorten(key, 9), _shorten(key, 8)))
    return out


def _make(sents, i, j, duration, score, tag, reason, hook, title) -> dict:
    return {"start": round(max(0.0, sents[i]["start"] - 0.2), 2),
            "end": round(min(duration, sents[j]["end"] + 0.35), 2),
            "score": int(max(0, min(100, score))), "tag": tag if tag in TAGS else "hook",
            "reason": reason.strip(), "hook": hook.strip(), "title": title.strip()}


SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_sentence": {"type": "integer"},
                    "end_sentence": {"type": "integer"},
                    "score": {"type": "integer"},
                    "reason_tag": {"type": "string", "enum": list(TAGS)},
                    "reason": {"type": "string"},
                    "hook": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["start_sentence", "end_sentence", "score", "reason_tag", "reason", "hook", "title"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}

SYSTEM = """Du bist ein erfahrener Short-Form-Editor. Du wählst aus langen Videos (Streams, Podcasts, Interviews) \
die Stellen aus, die als eigenständiger Clip auf TikTok, YouTube Shorts und Instagram Reels am besten laufen.

Ein guter Clip funktioniert ohne Vorwissen, fesselt in den ersten zwei Sekunden und endet mit einer Pointe, \
einer Auflösung oder einer klaren Aussage. Begrüßungen, Organisatorisches, Werbung und Verabschiedungen sind \
keine Clips. Wähle lieber weniger, dafür wirklich starke Stellen, und vergib die Punkte ehrlich: 90+ nur für \
Stellen, die du selbst sofort posten würdest, unter 50 für Füllmaterial.

Du bekommst das Transkript als nummerierte Sätze mit Zeitangaben. Clips beginnen und enden immer an Satzgrenzen: \
Gib den ersten und den letzten Satz jedes Clips über ihre Nummern an. Clips dürfen sich nicht überlappen.

Felder je Clip:
- score: Viral-Potenzial von 0 bis 100.
- reason_tag: der wichtigste Grund als Kategorie.
- reason: ein kurzer deutscher Satz, warum genau diese Stelle funktioniert.
- hook: Text, der in den ersten zwei Sekunden groß eingeblendet wird. Höchstens 8 Wörter, in der Sprache des \
Videos, macht neugierig, ohne die Pointe zu verraten.
- title: Arbeitstitel in der Sprache des Videos, höchstens 60 Zeichen."""


def find_with_claude(transcript: dict, loud: list[float], duration: float, cfg: dict) -> list[dict]:
    sents = to_sentences(transcript.get("words", []))
    if not sents:
        return []
    z = _zscores(loud)
    peaks, run_start = [], None
    for t, v in enumerate(z + [0.0]):
        if v >= 1.5 and run_start is None:
            run_start = t
        elif v < 1.5 and run_start is not None:
            peaks.append(f"{_fmt(run_start)}–{_fmt(t)}")
            run_start = None
    lines = [f"[{s['i']}] {_fmt(s['start'])}–{_fmt(s['end'])} ({s['start']:.1f}s–{s['end']:.1f}s): {s['text']}"
             for s in sents]
    user = (
        f"Videolänge: {_fmt(duration)}. Sprache laut Erkennung: {transcript.get('language') or 'unbekannt'}.\n"
        f"Gesucht: bis zu {cfg['num_suggestions']} Clips, jeder zwischen {cfg['clip_min_s']} und "
        f"{cfg['clip_max_s']} Sekunden lang. Wenn das Video dafür zu kurz ist, liefere weniger Clips.\n"
        f"Auffällig laute Stellen (mögliche Lacher, Rufe, Reaktionen): {', '.join(peaks[:60]) or 'keine'}.\n\n"
        "Transkript:\n" + "\n".join(lines)
    )
    data = ai.ask_json(SYSTEM, user, SCHEMA)
    mn, mx = float(cfg["clip_min_s"]), float(cfg["clip_max_s"])
    out, n = [], len(sents)
    for c in data.get("clips", []):
        try:
            i, j = int(c["start_sentence"]), int(c["end_sentence"])
        except (KeyError, TypeError, ValueError):
            continue
        i, j = max(0, min(n - 1, i)), max(0, min(n - 1, j))
        if j < i:
            i, j = j, i
        while j > i and sents[j]["end"] - sents[i]["start"] > mx * 1.15:      # zu lang: hinten kürzen
            j -= 1
        while j < n - 1 and sents[j]["end"] - sents[i]["start"] < mn * 0.6:   # zu kurz: hinten verlängern
            j += 1
        while i > 0 and sents[j]["end"] - sents[i]["start"] < mn * 0.6:       # am Videoende: vorne verlängern
            i -= 1
        out.append(_make(sents, i, j, duration, int(c.get("score", 50)), c.get("reason_tag", "hook"),
                         str(c.get("reason", "")), str(c.get("hook", "")), str(c.get("title", ""))))
    out.sort(key=lambda c: -c["score"])
    kept = []                       # Vorschläge, die sich stark überschneiden, nur einmal behalten (den besseren)
    for c in out:
        if all(min(c["end"], k["end"]) - max(c["start"], k["start"]) <= 0.5 * min(c["end"] - c["start"], k["end"] - k["start"])
               for k in kept):
            kept.append(c)
    return kept[: int(cfg["num_suggestions"])]


def find(transcript: dict, loud: list[float], duration: float, cfg: dict) -> tuple[list[dict], str, str]:
    """Gibt (Clips, Engine, Hinweis) zurück. Engine ist 'claude:<modell>' oder 'local'."""
    if ai.has_key():
        try:
            clips = find_with_claude(transcript, loud, duration, cfg)
            if clips:
                return clips, f"claude:{cfg['ai_model']}", ""
            note = "Die KI hat keine passenden Stellen geliefert. Stattdessen wurde die lokale Analyse verwendet."
        except ai.AIError as e:
            note = f"{e} Stattdessen wurde die lokale Analyse verwendet."
        return find_local(transcript, loud, duration, cfg), "local", note
    return (find_local(transcript, loud, duration, cfg), "local",
            "Ohne API-Key läuft nur die einfache lokale Analyse (Stichwörter und Lautstärke).")
