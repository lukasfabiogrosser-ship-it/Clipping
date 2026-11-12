"""Untertitel im Shorts-Stil (Wort für Wort hervorgehoben) und Hook-Einblendung."""
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config

W, H = 1080, 1920

TEMPLATES = {
    "pop": {"label": "Bold Pop", "desc": "Großbuchstaben, aktives Wort gelb", "font": "Montserrat-Black.ttf",
            "size": 84, "upper": True, "max_chars": 16, "max_words": 3, "color": (255, 255, 255),
            "active": (255, 214, 10), "stroke": (0, 0, 0), "stroke_w": 10, "style": "color", "scale": 1.12, "y": 0.70},
    "box": {"label": "Neon Box", "desc": "Aktives Wort im leuchtenden Kasten", "font": "Poppins-ExtraBold.ttf",
            "size": 76, "upper": False, "max_chars": 18, "max_words": 3, "color": (255, 255, 255),
            "active": (8, 14, 22), "box": (64, 220, 255), "stroke": (0, 0, 0), "stroke_w": 8, "style": "box",
            "scale": 1.0, "y": 0.72},
    "clean": {"label": "Clean", "desc": "Dezent, Wörter füllen sich nach und nach", "font": "Inter-Bold.ttf",
              "size": 62, "upper": False, "max_chars": 26, "max_words": 5, "color": (255, 255, 255),
              "active": (110, 228, 255), "stroke": (0, 0, 0), "stroke_w": 4, "style": "fill", "scale": 1.0,
              "y": 0.76},
    "impact": {"label": "Impact", "desc": "Sehr groß, zwei Wörter, aktives Wort grün", "font": "Anton-Regular.ttf",
               "size": 118, "upper": True, "max_chars": 13, "max_words": 2, "color": (255, 255, 255),
               "active": (57, 255, 136), "stroke": (0, 0, 0), "stroke_w": 12, "style": "color", "scale": 1.0,
               "y": 0.66},
}
DEFAULT_TEMPLATE = "pop"
HOOK_FONT = "Montserrat-ExtraBold.ttf"


@lru_cache(maxsize=64)
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(config.FONT_DIR / name), size)


@lru_cache(maxsize=8)
def _charset(name: str) -> frozenset:
    try:
        from fontTools.ttLib import TTFont
        return frozenset(TTFont(str(config.FONT_DIR / name)).getBestCmap())
    except Exception:
        return frozenset()


def _clean(text: str, font_name: str) -> str:
    """Zeichen entfernen, die die Schrift nicht kennt (z. B. Emojis)."""
    text = text.replace("’", "'").replace("„", '"').replace("“", '"').replace("”", '"').replace("…", "...")
    cs = _charset(font_name)
    if cs:
        text = "".join(ch for ch in text if ord(ch) in cs or ch == " ")
    return text.strip()


def group_words(words: list[dict], tpl: dict) -> list[dict]:
    """Wörter in kurze Blöcke teilen, die gleichzeitig eingeblendet werden."""
    groups, cur = [], []

    def flush():
        if cur:
            groups.append({"words": list(cur), "start": cur[0]["s"], "end": cur[-1]["e"]})
            cur.clear()

    for i, w in enumerate(words):
        chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
        if cur and (len(cur) >= tpl["max_words"] or chars > tpl["max_chars"] or w["s"] - cur[-1]["e"] > 0.7):
            flush()
        cur.append(w)
        if re.search(r"[.!?…]$", w["w"]):
            flush()
    flush()
    for k, g in enumerate(groups):          # Block bleibt stehen, bis der nächste kommt (bei kurzer Pause)
        nxt = groups[k + 1]["start"] if k + 1 < len(groups) else None
        g["show_until"] = nxt if nxt is not None and nxt - g["end"] <= 0.6 else g["end"] + 0.35
    return groups


def render_group(texts: tuple, active: int, tpl_name: str) -> np.ndarray:
    """Zeichnet einen Wortblock als RGBA-Bild. `active` ist der Index des gerade gesprochenen Wortes."""
    tpl = TEMPLATES[tpl_name]
    base = _font(tpl["font"], tpl["size"])
    big = _font(tpl["font"], int(tpl["size"] * tpl["scale"]))
    words = [(_clean(t, tpl["font"]).upper() if tpl["upper"] else _clean(t, tpl["font"])) for t in texts]
    words = [w if w else " " for w in words]
    space = base.getlength(" ") * (1.7 if tpl["style"] == "box" else 1.0)
    widths = [max(base.getlength(w), big.getlength(w)) for w in words]
    max_w = W - 120
    lines, line, lw = [], [], 0.0
    for i, ww in enumerate(widths):
        add = ww + (space if line else 0)
        if line and lw + add > max_w:
            lines.append(line)
            line, lw = [], 0.0
            add = ww
        line.append(i)
        lw += add
    if line:
        lines.append(line)
    asc, desc = big.getmetrics()
    line_h = int((asc + desc) * 1.02)
    pad = tpl["stroke_w"] + 28
    img_w = int(min(W, max(sum(widths[i] for i in ln) + space * (len(ln) - 1) for ln in lines) + pad * 2))
    img_h = line_h * len(lines) + pad * 2
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(img), ImageDraw.Draw(shadow)
    boxes = []
    for li, ln in enumerate(lines):
        total = sum(widths[i] for i in ln) + space * (len(ln) - 1)
        x = (img_w - total) / 2
        base_y = pad + li * line_h + asc
        for i in ln:
            is_active = i == active
            font = big if is_active else base
            cx = x + widths[i] / 2
            tw = font.getlength(words[i])
            pos = (cx - tw / 2, base_y)
            if tpl["style"] == "fill":
                color = tpl["active"] if is_active else tpl["color"]
                alpha = 255 if i <= active else 140
            elif is_active:
                color, alpha = tpl["active"], 255
            else:
                color, alpha = tpl["color"], 255
            if tpl["style"] == "box" and is_active:
                boxes.append((cx - tw / 2 - 16, base_y - asc * 0.86, cx + tw / 2 + 16, base_y + desc * 0.9))
            ds.text((pos[0], pos[1] + 6), words[i], font=font, fill=(0, 0, 0, 170), anchor="ls",
                    stroke_width=tpl["stroke_w"], stroke_fill=(0, 0, 0, 170))
            sw = 0 if (tpl["style"] == "box" and is_active) else tpl["stroke_w"]
            d.text(pos, words[i], font=font, fill=(*color, alpha), anchor="ls",
                   stroke_width=sw, stroke_fill=(*tpl["stroke"], alpha))
            x += widths[i] + space
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    if boxes:
        under = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        du = ImageDraw.Draw(under)
        for b in boxes:
            du.rounded_rectangle(b, radius=18, fill=(*tpl["box"], 255))
        shadow = Image.alpha_composite(shadow, under)
    return np.asarray(Image.alpha_composite(shadow, img))


def render_hook(text: str) -> np.ndarray | None:
    """Hook-Text als weißer Kasten mit dunkler Schrift (oben im Bild)."""
    text = _clean(text, HOOK_FONT).upper()
    if not text:
        return None
    size = 62 if len(text) <= 34 else 52
    font = _font(HOOK_FONT, size)
    max_w = W - 220
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if cur and font.getlength(trial) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    lines = lines[:4]
    asc, desc = font.getmetrics()
    line_h = int((asc + desc) * 1.08)
    tw = max(font.getlength(ln) for ln in lines)
    px, py, m = 40, 26, 30
    bw, bh = int(tw + px * 2), int(line_h * len(lines) + py * 2)
    img = Image.new("RGBA", (bw + m * 2, bh + m * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((m, m + 8, m + bw, m + bh + 8), radius=26, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((m, m, m + bw, m + bh), radius=26, fill=(255, 255, 255, 250))
    for i, ln in enumerate(lines):
        d.text((m + bw / 2, m + py + i * line_h + asc), ln, font=font, fill=(10, 14, 20, 255), anchor="ms")
    return np.asarray(img)


def blend(frame: np.ndarray, overlay: np.ndarray, cx: float, cy: float, scale: float = 1.0, opacity: float = 1.0):
    """Legt ein RGBA-Bild (RGB-Reihenfolge) mittig bei (cx, cy) auf ein BGR-Bild."""
    import cv2
    if scale != 1.0:
        overlay = cv2.resize(overlay, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    oh, ow = overlay.shape[:2]
    x0, y0 = int(round(cx - ow / 2)), int(round(cy - oh / 2))
    fx0, fy0 = max(0, x0), max(0, y0)
    fx1, fy1 = min(frame.shape[1], x0 + ow), min(frame.shape[0], y0 + oh)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    part = overlay[fy0 - y0: fy1 - y0, fx0 - x0: fx1 - x0]
    alpha = part[:, :, 3:4].astype(np.float32) * (opacity / 255.0)
    region = frame[fy0:fy1, fx0:fx1].astype(np.float32)
    rgb = part[:, :, 2::-1].astype(np.float32)          # RGB -> BGR
    frame[fy0:fy1, fx0:fx1] = (region * (1 - alpha) + rgb * alpha).astype(np.uint8)


class CaptionRenderer:
    """Zeichnet für einen Zeitpunkt den passenden Untertitel-Block auf das Bild."""

    def __init__(self, words: list[dict], template: str):
        self.tpl_name = template if template in TEMPLATES else DEFAULT_TEMPLATE
        self.tpl = TEMPLATES[self.tpl_name]
        self.groups = group_words(words, self.tpl)
        self._cache = {}
        self._gi = 0

    def draw(self, frame: np.ndarray, t: float):
        gs = self.groups
        while self._gi < len(gs) - 1 and t >= gs[self._gi]["show_until"] and t >= gs[self._gi + 1]["start"] - 0.001:
            self._gi += 1
        if not gs:
            return
        g = gs[self._gi]
        if t < g["start"] or t >= g["show_until"]:
            return
        active = 0
        for i, w in enumerate(g["words"]):
            if t >= w["s"]:
                active = i
        key = (self._gi, active)
        if key not in self._cache:
            if len(self._cache) > 40:
                self._cache.clear()
            self._cache[key] = render_group(tuple(w["w"] for w in g["words"]), active, self.tpl_name)
        age = t - g["start"]
        scale = 0.86 + 0.14 * min(1.0, age / 0.10) if age < 0.10 else 1.0     # kurzes „Aufpoppen“
        blend(frame, self._cache[key], W / 2, H * self.tpl["y"], scale)
