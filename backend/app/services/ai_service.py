"""Multi-provider AI client.

Supports any OpenAI-compatible API:
  - OpenAI            (default)
  - OpenRouter        (free + paid models from many providers)
  - Groq              (free tier, very fast)
  - Together AI       (free tier on some models)
  - Local (Ollama, LM Studio, vLLM)

Falls back to a deterministic stub when no API key is configured so the rest of
the app keeps working in offline / dev mode.

Provider is auto-detected from AI_PROVIDER env var, or by inspecting the API
key prefix:
  - sk-or-...    -> OpenRouter
  - gsk_...      -> Groq
  - sk-...       -> OpenAI
  - tg-...       -> Together AI
"""

from __future__ import annotations
import json
from typing import Any

from openai import AsyncOpenAI
from ..config import settings


# Provider configs: base_url + a sensible default model for each.
PROVIDER_CONFIG = {
    "openai": {
        "base_url": None,  # use SDK default
        "default_model": "gpt-4o-mini",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.1",
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
    },
}


def _detect_provider() -> str:
    """Pick provider from env var or API key prefix."""
    explicit = (getattr(settings, "ai_provider", "") or "").lower().strip()
    if explicit in PROVIDER_CONFIG:
        return explicit

    key = (settings.openai_api_key or "").strip()
    if key.startswith("sk-or-"):
        return "openrouter"
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("tg-") or key.startswith("tg_"):
        return "together"
    if key.startswith("sk-"):
        return "openai"
    # No key but a custom base_url? Probably a local model
    if getattr(settings, "ai_base_url", ""):
        return "ollama"
    return "openai"


_client: AsyncOpenAI | None = None
_resolved_model: str | None = None


def _get_client() -> tuple[AsyncOpenAI | None, str]:
    """Return (client, model). Client is None if provider not configured."""
    global _client, _resolved_model

    provider = _detect_provider()
    config = PROVIDER_CONFIG[provider]

    # Local providers (ollama, lmstudio) don't require a key
    needs_key = provider not in ("ollama", "lmstudio")
    api_key = settings.openai_api_key or ""
    if needs_key and not api_key:
        return None, ""

    # Resolve model
    explicit_model = (settings.openai_model or "").strip()
    model = explicit_model or config["default_model"]

    if _client is None:
        # Allow custom base_url override from settings.ai_base_url
        base_url = getattr(settings, "ai_base_url", "") or config["base_url"]
        _client = AsyncOpenAI(
            api_key=api_key or "no-key-needed",
            base_url=base_url,
        )
        _resolved_model = model

    return _client, _resolved_model or model


async def chat_json(prompt: str, system: str = "You are a helpful assistant.") -> dict[str, Any]:
    """Run a JSON-mode completion. Returns a dict, possibly empty on failure.

    Note: not every provider/model supports response_format=json_object. We try
    it first, and if the request errors, retry without that constraint and
    parse the text response as JSON manually.
    """
    client, model = _get_client()
    if client is None:
        return {}

    messages = [
        {"role": "system", "content": system + "\n\nALWAYS respond with valid JSON only. No prose, no markdown."},
        {"role": "user", "content": prompt},
    ]

    # First attempt with json_object response format
    try:
        resp = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=messages,
            temperature=0.3,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception:
        pass

    # Fallback: plain text + parse
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        content = resp.choices[0].message.content or "{}"
        # Strip code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        # Find first { and last }
        if "{" in content and "}" in content:
            start = content.index("{")
            end = content.rindex("}") + 1
            content = content[start:end]
        return json.loads(content)
    except Exception:
        return {}


async def chat_text(prompt: str, system: str = "You are a helpful assistant.") -> str:
    client, model = _get_client()
    if client is None:
        return ""
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
        )
        return resp.choices[0].message.content or ""
    except Exception:
        return ""


def get_provider_info() -> dict[str, Any]:
    """For debugging / status endpoints."""
    provider = _detect_provider()
    config = PROVIDER_CONFIG[provider]
    has_key = bool(settings.openai_api_key) or provider in ("ollama", "lmstudio")
    return {
        "provider": provider,
        "model": settings.openai_model or config["default_model"],
        "baseUrl": getattr(settings, "ai_base_url", "") or config["base_url"] or "https://api.openai.com/v1",
        "configured": has_key,
    }
