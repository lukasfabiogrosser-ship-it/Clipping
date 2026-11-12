"""Transkription mit faster-whisper (lokal), mit Zeitstempel pro Wort."""
import os
import re
import threading

import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")          # Modell-Download über normales HTTPS
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

_models = {}
_lock = threading.Lock()


class TranscribeError(Exception):
    pass


def device_info() -> dict:
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return {"device": "cuda", "compute_type": "float16", "label": "Grafikkarte (CUDA)"}
    except Exception:
        pass
    return {"device": "cpu", "compute_type": "int8", "label": "Prozessor (CPU)"}


def get_model(name: str):
    with _lock:
        if name not in _models:
            from faster_whisper import WhisperModel
            d = device_info()
            try:
                _models[name] = WhisperModel(name, device=d["device"], compute_type=d["compute_type"])
            except Exception as e:
                if d["device"] == "cuda":       # Grafikkarte vorhanden, aber Treiber/Bibliotheken fehlen
                    try:
                        _models[name] = WhisperModel(name, device="cpu", compute_type="int8")
                        return _models[name]
                    except Exception as e2:
                        e = e2
                raise TranscribeError(
                    f"Das Sprachmodell „{name}“ konnte nicht geladen werden. Beim ersten Mal wird es aus dem "
                    f"Internet heruntergeladen – bitte Verbindung prüfen. ({type(e).__name__}: {e})") from e
        return _models[name]


def transcribe(audio: np.ndarray, model_name: str, language: str = "auto", progress=None) -> dict:
    """Gibt {language, segments:[{start,end,text}], words:[{w,s,e}]} zurück."""
    duration = len(audio) / 16000.0
    if duration < 0.5:
        return {"language": language if language != "auto" else "", "segments": [], "words": []}
    model = get_model(model_name)
    segs, info = model.transcribe(
        audio, language=None if language == "auto" else language, word_timestamps=True,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}, beam_size=5,
        condition_on_previous_text=False)
    segments, words = [], []
    for s in segs:
        text = s.text.strip()
        if not text:
            continue
        segments.append({"start": round(float(s.start), 2), "end": round(float(s.end), 2), "text": text})
        for w in s.words or []:
            token = w.word.strip()
            if token:
                words.append({"w": token, "s": round(float(w.start), 2), "e": round(float(w.end), 2)})
        if progress:
            progress(min(1.0, float(s.end) / duration))
    return {"language": info.language, "segments": segments, "words": words}


_END = re.compile(r"[.!?…]+[\"'”“)\]]*$")


def sentences(words: list[dict], max_words: int = 45, gap: float = 1.2) -> list[dict]:
    """Wörter zu Sätzen bündeln (Satzzeichen, lange Pause oder Maximallänge)."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end = bool(_END.search(w["w"])) or nxt is None or (nxt["s"] - w["e"] > gap) or len(cur) >= max_words
        if end:
            out.append({"i": len(out), "start": cur[0]["s"], "end": cur[-1]["e"],
                        "text": " ".join(x["w"] for x in cur)})
            cur = []
    return out
