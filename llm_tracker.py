"""Lightweight LLM usage tracker for existing bots.

Copy this file to your bot project and call track_*() after each LLM API call.

Required env vars:
    MONITOR_URL      — e.g. https://bot-monitor.up.railway.app
    MONITOR_API_KEY  — shared secret

Usage examples:
    # Anthropic
    response = client.messages.create(...)
    track_anthropic("my-bot", response)

    # OpenAI
    response = client.chat.completions.create(...)
    track_openai("my-bot", response)

    # Gemini
    response = model.generate_content(...)
    track_gemini("my-bot", response, model="gemini-2.5-flash")
"""

import json
import logging
import os
import threading
import urllib.request

logger = logging.getLogger(__name__)

def _get_url():
    return os.environ.get("MONITOR_URL", "")

def _get_key():
    return os.environ.get("MONITOR_API_KEY", "")


def _post_usage(payload: dict):
    """Fire-and-forget POST in a daemon thread."""
    url = _get_url()
    if not url:
        return

    def _send():
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{url}/api/llm-usage",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.debug("LLM tracking failed (ignored): %s", e)

    t = threading.Thread(target=_send, daemon=True)
    t.start()


def track_anthropic(bot_name: str, response):
    """Track Anthropic (Claude) API response.

    response.usage.input_tokens / output_tokens
    response.model -> e.g. "claude-sonnet-4-5-20250929"
    """
    try:
        _post_usage({
            "bot_name": bot_name,
            "api_key": _get_key(),
            "provider": "anthropic",
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        })
    except Exception as e:
        logger.debug("track_anthropic failed (ignored): %s", e)


def track_openai(bot_name: str, response, provider: str = "openai"):
    """Track OpenAI-compatible API response.

    response.usage.prompt_tokens / completion_tokens
    response.model -> e.g. "gpt-4o-2024-08-06"
    """
    try:
        _post_usage({
            "bot_name": bot_name,
            "api_key": _get_key(),
            "provider": provider,
            "model": response.model,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        })
    except Exception as e:
        logger.debug("track_openai failed (ignored): %s", e)


def track_gemini(bot_name: str, response, model: str = "gemini-2.5-flash"):
    """Track Google Gemini API response (both old and new SDK).

    Old SDK (google.generativeai): response.usage_metadata.prompt_token_count / candidates_token_count
    New SDK (google.genai):        response.usage_metadata.prompt_token_count / candidates_token_count
    """
    try:
        meta = response.usage_metadata
        # Handle both dict-like and object-like access
        if hasattr(meta, "prompt_token_count"):
            inp = meta.prompt_token_count or 0
            out = meta.candidates_token_count or 0
        else:
            inp = getattr(meta, "prompt_tokens", 0) or 0
            out = getattr(meta, "candidates_tokens", 0) or 0
        _post_usage({
            "bot_name": bot_name,
            "api_key": _get_key(),
            "provider": "gemini",
            "model": model,
            "input_tokens": inp,
            "output_tokens": out,
        })
    except Exception as e:
        logger.debug("track_gemini failed (ignored): %s", e)


def track_groq(bot_name: str, response):
    """Track Groq API response (OpenAI-compatible)."""
    track_openai(bot_name, response, provider="groq")


def track_grok(bot_name: str, response):
    """Track xAI Grok API response (OpenAI-compatible)."""
    track_openai(bot_name, response, provider="xai")
