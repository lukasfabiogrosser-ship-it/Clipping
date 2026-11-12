"""Titel, Beschreibung und Hashtags je Plattform."""
import re
from collections import Counter

from . import ai

PLATFORMS = {"youtube": "YouTube Shorts", "tiktok": "TikTok", "instagram": "Instagram Reels"}

_ITEM = {
    "type": "object",
    "properties": {
        "titles": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titles", "description", "hashtags"],
    "additionalProperties": False,
}
SCHEMA = {"type": "object", "properties": {k: _ITEM for k in PLATFORMS}, "required": list(PLATFORMS),
          "additionalProperties": False}

SYSTEM = """Du schreibst Texte für kurze Hochkant-Videos. Du bekommst das Transkript eines Clips und lieferst \
für jede Plattform genau drei Titelvorschläge, eine Beschreibung und Hashtags – in der Sprache des Clips.

Gute Titel machen neugierig, ohne zu lügen, und verraten die Pointe nicht. Kein Clickbait, das der Clip nicht \
einlöst. Hashtags ohne Leerzeichen, jeweils mit führendem #.

- YouTube Shorts: Titel höchstens 70 Zeichen, wichtigstes Stichwort vorn. Beschreibung ein bis zwei Sätze. \
Drei bis fünf Hashtags, darunter #shorts.
- TikTok: Die „Titel“ sind hier Varianten der ersten Zeile der Caption, kurz und direkt. Beschreibung ein Satz. \
Drei bis fünf Hashtags.
- Instagram Reels: Die „Titel“ sind Varianten der ersten Zeile der Caption. Beschreibung zwei bis drei Sätze mit \
einer Frage oder Aufforderung am Ende. Fünf bis acht Hashtags.

Wenn Kampagnenregeln angegeben sind (Pflicht-Hashtags, Erwähnungen, verbotene Wörter), halte sie strikt ein."""

STOP = set("""aber alle allem allen aller alles also andere anderen auch beim bereits bevor damit dann danach dass
dein deine diese diesem diesen dieser dieses doch dort durch eine einem einen einer eines einfach einmal etwas euch
euer eure ganz ganze gegen genau gerade gibt habe haben hatte hätte heute hier immer jeden jetzt kann kein keine
können könnte machen macht mehr mein meine nach nicht nichts noch oder ohne schon sehr seid sein seine seit sich
sind sollte über unter viel viele vielleicht waren warum weil weiter welche wenn werden wieder will wird wirklich
worden würde würdest zwischen about after again also been before being could does doing each from have having here
into just more most much only other over really should some such than that their them then there these they this
those through very what when where which while will with would your yours""".split())


def _hashtag(word: str) -> str:
    return "#" + re.sub(r"[^0-9A-Za-zÄÖÜäöüß]", "", word).lower()


def local(text: str, hook: str, title: str) -> dict:
    """Einfache Vorschläge ohne KI: aus Hook, erstem und letztem Satz und häufigen Wörtern."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()]

    def short(s: str, n: int = 68) -> str:
        s = s.strip()
        return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"

    cands = [hook, title] + ([sents[-1], sents[0]] if sents else [])
    titles = []
    for c in cands:
        c = short(c or "")
        key = re.sub(r"\W+", "", c.lower())[:24]
        if c and key not in [re.sub(r"\W+", "", t.lower())[:24] for t in titles]:
            titles.append(c[0].upper() + c[1:])
    desc = short(" ".join(sents[:2]), 180)
    desc = desc[:1].upper() + desc[1:]
    # Hashtags: im Deutschen sind Hauptwörter mitten im Satz großgeschrieben – die taugen am ehesten.
    nouns = Counter()
    for s in sents:
        for w in re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", s)[1:]:
            if w[0].isupper() and w.lower() not in STOP:
                nouns[w.lower()] += 1
    common = [w for w, _ in sorted(nouns.items(), key=lambda kv: (-kv[1], -len(kv[0])))[:4]]
    if len(common) < 3:
        words = [w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß]{5,}", text)]
        for w, _ in Counter(w for w in words if w not in STOP).most_common(6):
            if w not in common and len(common) < 4:
                common.append(w)
    tags = [_hashtag(w) for w in common]
    extra = {"youtube": ["#shorts"], "tiktok": ["#fyp", "#viral"], "instagram": ["#reels", "#reelsinstagram"]}
    return {p: {"titles": titles[:3], "description": desc, "hashtags": tags + extra[p]} for p in PLATFORMS}


def generate(text: str, hook: str, title: str, language: str, rules: str = "") -> tuple[dict, str, str]:
    """Gibt (Texte, Engine, Hinweis) zurück."""
    if not ai.has_key():
        return local(text, hook, title), "local", "Einfache Vorschläge ohne KI. Mit API-Key schreibt Claude die Texte."
    user = (f"Sprache des Clips: {language or 'unbekannt'}\nHook-Einblendung: {hook or '–'}\n"
            f"Kampagnenregeln: {rules.strip() or 'keine'}\n\nTranskript des Clips:\n{text}")
    try:
        data = ai.ask_json(SYSTEM, user, SCHEMA, max_tokens=8000, effort="low")
    except ai.AIError as e:
        return local(text, hook, title), "local", f"{e} Stattdessen einfache Vorschläge ohne KI."
    out = {}
    for p in PLATFORMS:
        item = data.get(p) or {}
        tags = []
        for h in item.get("hashtags", []):
            h = _hashtag(str(h))
            if len(h) > 1 and h not in tags:
                tags.append(h)
        out[p] = {"titles": [str(t).strip() for t in item.get("titles", []) if str(t).strip()][:3],
                  "description": str(item.get("description", "")).strip(), "hashtags": tags}
    from . import config
    return out, f"claude:{config.load_settings()['ai_model']}", ""
