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

GEMINI_MODEL = "gemini-2.5-pro"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

MAX_RETRIES = 1
TIMEOUT_SECONDS = 30


def _encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def _call_gemini(prompt: str, image_bytes: bytes) -> dict:
    api_key = st.secrets["GEMINI_API_KEY"]
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
    response = requests.post(
        f"{GEMINI_URL}?key={api_key}",
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
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
        except Exception as e:
            last_error = str(e)
            time.sleep(1)
            continue

    return {
        "success": False,
        "model_used": None,
        "text": None,
        "error": last_error,
    }
