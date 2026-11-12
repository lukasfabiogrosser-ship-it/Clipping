"""Anbindung an die Claude-API (Anthropic). Der Key kommt nur aus den Einstellungen."""
import json
import os

from . import config


class AIError(Exception):
    """Fehler mit einer Meldung, die man dem Nutzer direkt zeigen kann."""


def has_key() -> bool:
    return bool(config.load_settings().get("anthropic_api_key"))


def _client():
    import anthropic
    s = config.load_settings()
    key = s.get("anthropic_api_key")
    if not key:
        raise AIError("Es ist kein Anthropic-API-Key eingetragen (Einstellungen → KI).")
    base = os.environ.get("CLIPPILOT_ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    return anthropic.Anthropic(api_key=key, base_url=base, max_retries=2), s["ai_model"]


def _friendly(e) -> AIError:
    import anthropic
    if isinstance(e, anthropic.AuthenticationError):
        return AIError("Der API-Key wurde abgelehnt. Bitte in den Einstellungen prüfen.")
    if isinstance(e, anthropic.PermissionDeniedError):
        return AIError("Dieser API-Key darf das gewählte Modell nicht benutzen.")
    if isinstance(e, anthropic.NotFoundError):
        return AIError("Das gewählte KI-Modell ist für diesen Key nicht verfügbar.")
    if isinstance(e, anthropic.RateLimitError):
        return AIError("Zu viele Anfragen oder Guthaben aufgebraucht. Bitte später erneut versuchen.")
    if isinstance(e, anthropic.APIConnectionError):
        return AIError("Keine Verbindung zur Claude-API. Bitte Internetverbindung prüfen.")
    if isinstance(e, anthropic.APIStatusError):
        return AIError(f"Die Claude-API meldet einen Fehler ({e.status_code}): {getattr(e, 'message', e)}")
    return AIError(f"KI-Fehler: {e}")


def test_key() -> dict:
    """Prüft Key und Modell, ohne Tokens zu verbrauchen."""
    import anthropic
    try:
        client, model = _client()
        m = client.models.retrieve(model)
        return {"ok": True, "message": f"Verbindung steht. Modell: {getattr(m, 'display_name', model)}"}
    except AIError as e:
        return {"ok": False, "message": str(e)}
    except anthropic.APIError as e:
        return {"ok": False, "message": str(_friendly(e))}


def ask_json(system: str, user: str, schema: dict, max_tokens: int = 32000, effort: str = "medium") -> dict:
    """Eine Anfrage, deren Antwort garantiert dem JSON-Schema entspricht."""
    import anthropic
    client, model = _client()
    kwargs = dict(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    # Lehnt ein Sicherheitsfilter die Anfrage ab, übernimmt automatisch ein Ersatzmodell.
    use_fallback = not model.startswith("claude-haiku")
    try:
        try:
            if use_fallback:
                with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"],
                                                 fallbacks="default", **kwargs) as stream:
                    msg = stream.get_final_message()
            else:
                with client.messages.stream(**kwargs) as stream:
                    msg = stream.get_final_message()
        except anthropic.BadRequestError as e:
            if not use_fallback or "fallback" not in str(e).lower():
                raise
            with client.messages.stream(**kwargs) as stream:
                msg = stream.get_final_message()
    except anthropic.APIError as e:
        raise _friendly(e) from e

    if msg.stop_reason == "refusal":
        raise AIError("Die KI hat diese Anfrage abgelehnt (Inhaltsfilter).")
    if msg.stop_reason == "max_tokens":
        raise AIError("Die KI-Antwort war zu lang und wurde abgeschnitten.")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except ValueError as e:
        raise AIError("Die KI-Antwort konnte nicht gelesen werden.") from e
