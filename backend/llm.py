"""LLM wrapper. Gemini Studio first, Anthropic as fallback. Easy to swap."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.config import get_settings

logger = logging.getLogger("pathway.llm")

T = TypeVar("T", bound=BaseModel)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class LlmError(RuntimeError):
    """Raised when the language model cannot complete a request."""


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    start_arr = text.find("[")
    if start == -1 and start_arr == -1:
        return text
    if start == -1 or (start_arr != -1 and start_arr < start):
        end = text.rfind("]")
        return text[start_arr : end + 1] if end != -1 else text
    end = text.rfind("}")
    return text[start : end + 1] if end != -1 else text


def _gemini_complete(system: str, user: str, temperature: float, json_mode: bool) -> str:
    settings = get_settings()
    key = settings.google_key
    if not key:
        raise LlmError("No Gemini API key configured")
    model = settings.llm_model
    if model.lower().startswith("claude"):
        model = "gemini-2.0-flash"
    url = GEMINI_URL.format(model=model)
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 8192,
        },
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    with httpx.Client(timeout=settings.http_timeout) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    parts = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    texts = [p.get("text", "") for p in parts if "text" in p]
    if not texts:
        raise LlmError("Gemini returned no text")
    return "".join(texts)


def _anthropic_complete(system: str, user: str, temperature: float, json_mode: bool) -> str:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LlmError("No Anthropic API key configured")
    model = settings.llm_model
    if not model.lower().startswith("claude"):
        model = "claude-sonnet-4-5"
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 8192,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    with httpx.Client(timeout=settings.http_timeout) as client:
        resp = client.post(ANTHROPIC_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    blocks = data.get("content", [])
    texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    if not texts:
        raise LlmError("Anthropic returned no text")
    return "".join(texts)


def complete(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """Call the configured LLM and return raw text."""
    settings = get_settings()
    last_error: Exception | None = None
    if settings.google_key:
        try:
            return _gemini_complete(system, user, temperature, json_mode)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("Gemini call failed: %s", exc)
    if settings.anthropic_api_key:
        try:
            extra = "\n\nReturn valid JSON only." if json_mode else ""
            return _anthropic_complete(system, user + extra, temperature, json_mode)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("Anthropic call failed: %s", exc)
    raise LlmError(str(last_error) if last_error else "No LLM API key configured")


def complete_json(
    system: str,
    user: str,
    schema: type[T],
    *,
    temperature: float = 0.2,
) -> T:
    """Ask for JSON, validate with Pydantic, retry once on invalid JSON."""
    raw = complete(system, user, temperature=temperature, json_mode=True)
    for attempt in (1, 2):
        try:
            payload = json.loads(_extract_json_text(raw))
            return schema.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.info("JSON validation failed (attempt %s): %s", attempt, exc)
            if attempt == 2:
                raise LlmError(f"Model did not return valid JSON: {exc}") from exc
            raw = complete(
                system,
                user
                + "\n\nYour previous reply was not valid JSON matching the schema. "
                "Reply again with valid JSON only.",
                temperature=0.1,
                json_mode=True,
            )
    raise LlmError("JSON retry exhausted")
