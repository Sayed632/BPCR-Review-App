"""
core/model_router.py
Calls Google's Gemini API directly (no OpenRouter) for vision/
handwriting extraction. Switched from OpenRouter's multi-model
fallback chain to unblock testing on Gemini's free tier - trade-off
is no automatic fallback to GPT-4o/Claude if Gemini is unavailable.
"""

import base64
import time
import requests
import streamlit as st

# gemini-2.5-flash has a much higher free-tier rate limit than
# gemini-2.5-pro (which allows only a handful of requests/minute) and is
# still strong on handwriting/vision extraction. Since this app fires one
# call per field, pro's quota gets exhausted almost immediately on any
# page with more than a couple of fields. Switch back to "pro" only if
# you're on a paid tier and need the extra accuracy.
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

MAX_RETRIES = 4
TIMEOUT_SECONDS = 30
BASE_BACKOFF_SECONDS = 5  # doubles each retry: 5s, 10s, 20s, 40s


def _encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


class GeminiCallError(Exception):
    """Raised for any failed Gemini call. Message is always pre-sanitized —
    never built from a raw requests exception, which can embed the request
    URL (and therefore the API key, if it were ever passed as a query
    param) in its string form."""


class RateLimitError(GeminiCallError):
    """429 specifically - callers should back off, not retry instantly."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _get_api_key() -> str:
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        raise GeminiCallError(
            "GEMINI_API_KEY is missing from Secrets. Add it under "
            "App settings -> Secrets (Streamlit Cloud) or .streamlit/secrets.toml (local)."
        )
    if not api_key.startswith("AIzaSy"):
        # Not a hard failure (Google could change the prefix), but this is
        # the #1 cause of "every field failed at once" - a key that's been
        # mis-pasted, truncated, or is actually some other service's key.
        st.warning(
            "GEMINI_API_KEY doesn't look like a standard Google AI Studio key "
            "(these normally start with 'AIzaSy'). If every extraction is "
            "failing, double-check this value first.",
            icon="⚠️",
        )
    return api_key


def _call_gemini(prompt: str, image_bytes: bytes) -> dict:
    api_key = _get_api_key()
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": _encode_image(image_bytes),
                        }
                    },
                ]
            }
        ]
    }
    try:
        # Key goes in a header, never the URL - so it can't end up in a
        # requests exception's string form (which includes the request URL)
        # or in any proxy/browser/server access log that captures full URLs.
        response = requests.post(
            GEMINI_URL,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException:
        # Network-level failure (timeout, DNS, connection reset, etc).
        # No response object to inspect - message is safe by construction.
        raise GeminiCallError("Network error calling Gemini API (timeout or connection failure).")

    if not response.ok:
        # Build the error message ourselves from status + response body only.
        # Never touch response.url or raise_for_status()'s exception text -
        # both can contain the full request URL.
        try:
            body = response.json()
            api_message = body.get("error", {}).get("message", "")
        except ValueError:
            api_message = response.text[:300]

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                f"Gemini API rate limit hit: {api_message}",
                retry_after=float(retry_after) if retry_after else None,
            )
        raise GeminiCallError(f"Gemini API error {response.status_code}: {api_message}")

    return response.json()


def extract_field(prompt: str, image_bytes: bytes) -> dict:
    """
    Same interface as before so extractor.py needs no changes.
    Returns {"success", "model_used", "text", "raw"} or
    {"success": False, "model_used": None, "text": None, "error"}.
    """
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            result = _call_gemini(prompt, image_bytes)
            text_output = result["candidates"][0]["content"]["parts"][0]["text"]
            return {
                "success": True,
                "model_used": GEMINI_MODEL,
                "text": text_output,
                "raw": result,
            }
        except RateLimitError as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                wait = e.retry_after or (BASE_BACKOFF_SECONDS * (2 ** attempt))
                time.sleep(wait)
            continue
        except GeminiCallError as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                time.sleep(1)
            continue
        except (KeyError, IndexError):
            # Response came back 200 OK but wasn't shaped as expected
            # (e.g. blocked by a safety filter with no candidates).
            last_error = "Gemini returned an unexpected response shape (possibly content-filtered)."
            if attempt < MAX_RETRIES:
                time.sleep(1)
            continue

    return {
        "success": False,
        "model_used": None,
        "text": None,
        "error": last_error,
    }
