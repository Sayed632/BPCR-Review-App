"""
core/model_router.py
Calls OpenRouter's chat completions API (OpenAI-compatible) for vision/
handwriting extraction, trying a chain of free vision-capable models in
order and falling back automatically if one is rate-limited, delisted,
or otherwise unavailable. OpenRouter's free-model roster changes often,
so don't assume this list stays accurate forever - check
https://openrouter.ai/models?fmt=cards&max_price=0 periodically and
update FALLBACK_MODELS if a model here has been pulled.
"""

import base64
import time
import requests
import streamlit as st

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Ordered fallback chain of free, vision-capable models (as of Aug 2026).
# extract_field() tries each in order and moves to the next on failure,
# so a single delisted/rate-limited model doesn't take the whole app down.
FALLBACK_MODELS = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]

MAX_RETRIES_PER_MODEL = 2
TIMEOUT_SECONDS = 30
BASE_BACKOFF_SECONDS = 5  # doubles each retry: 5s, 10s


def _encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


class OpenRouterCallError(Exception):
    """Raised for any failed OpenRouter call. Message is always
    pre-sanitized — never built from a raw requests exception, which can
    embed request details. The key is sent as a header (Authorization:
    Bearer ...), never as a URL query param, so it can't leak into a
    URL-based log or error message."""


class RateLimitError(OpenRouterCallError):
    """429 specifically - caller should back off before retrying."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ModelUnavailableError(OpenRouterCallError):
    """404 / model not found - this model was likely delisted. Caller
    should move to the next model in the fallback chain rather than
    retrying the same one."""


def _get_api_key() -> str:
    api_key = st.secrets.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise OpenRouterCallError(
            "OPENROUTER_API_KEY is missing from Secrets. Add it under "
            "App settings -> Secrets (Streamlit Cloud) or .streamlit/secrets.toml (local)."
        )
    return api_key


def _call_model(model: str, prompt: str, image_bytes: bytes) -> dict:
    api_key = _get_api_key()
    b64_image = _encode_image(image_bytes)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                    },
                ],
            }
        ],
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                # Optional but recommended by OpenRouter for their own
                # analytics/rate-limit tracking - not required to work.
                "X-Title": "BPCR Review App",
            },
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException:
        raise OpenRouterCallError("Network error calling OpenRouter (timeout or connection failure).")

    if not response.ok:
        try:
            body = response.json()
            api_message = body.get("error", {}).get("message", "")
        except ValueError:
            api_message = response.text[:300]

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                f"OpenRouter rate limit hit on {model}: {api_message}",
                retry_after=float(retry_after) if retry_after else None,
            )
        if response.status_code == 404:
            raise ModelUnavailableError(f"Model {model} not found (likely delisted): {api_message}")
        raise OpenRouterCallError(f"OpenRouter error {response.status_code} on {model}: {api_message}")

    return response.json()


def extract_field(prompt: str, image_bytes: bytes) -> dict:
    """
    Same interface as before so extractor.py needs no changes.
    Tries each model in FALLBACK_MODELS in order. Returns
    {"success", "model_used", "text", "raw"} or
    {"success": False, "model_used": None, "text": None, "error"}.
    """
    last_error = None

    for model in FALLBACK_MODELS:
        for attempt in range(MAX_RETRIES_PER_MODEL + 1):
            try:
                result = _call_model(model, prompt, image_bytes)
                text_output = result["choices"][0]["message"]["content"]
                return {
                    "success": True,
                    "model_used": model,
                    "text": text_output,
                    "raw": result,
                }
            except ModelUnavailableError as e:
                # No point retrying the same delisted model - move on.
                last_error = str(e)
                break
            except RateLimitError as e:
                last_error = str(e)
                if attempt < MAX_RETRIES_PER_MODEL:
                    wait = e.retry_after or (BASE_BACKOFF_SECONDS * (2 ** attempt))
                    time.sleep(wait)
                continue
            except OpenRouterCallError as e:
                last_error = str(e)
                if attempt < MAX_RETRIES_PER_MODEL:
                    time.sleep(1)
                continue
            except (KeyError, IndexError):
                last_error = f"{model} returned an unexpected response shape (possibly content-filtered)."
                if attempt < MAX_RETRIES_PER_MODEL:
                    time.sleep(1)
                continue
        # exhausted retries for this model (or it was unavailable) - try next model

    return {
        "success": False,
        "model_used": None,
        "text": None,
        "error": last_error,
    }
