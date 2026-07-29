"""
model_router.py
Routes vision/handwriting extraction calls through OpenRouter,
with automatic fallback if the primary model fails.
"""

import base64
import time
import requests
import streamlit as st

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Ordered list: primary first, fallbacks after.
# All must support image/vision input.
MODEL_CHAIN = [
    "google/gemini-2.5-pro",
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4.5",
]

MAX_RETRIES_PER_MODEL = 1
TIMEOUT_SECONDS = 30


def _encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def _call_model(model_name: str, prompt: str, image_bytes: bytes) -> dict:
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{_encode_image(image_bytes)}"
                        },
                    },
                ],
            }
        ],
    }
    response = requests.post(
        OPENROUTER_URL, headers=headers, json=payload, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response.json()


def extract_field(prompt: str, image_bytes: bytes) -> dict:
    """
    Tries each model in MODEL_CHAIN in order until one succeeds.
    Returns extracted text plus which model actually served the request
    (important for audit trail when reviewers question a reading).
    """
    last_error = None

    for model_name in MODEL_CHAIN:
        for attempt in range(MAX_RETRIES_PER_MODEL + 1):
            try:
                result = _call_model(model_name, prompt, image_bytes)
                text_output = result["choices"][0]["message"]["content"]
                return {
                    "success": True,
                    "model_used": model_name,
                    "text": text_output,
                    "raw": result,
                }
            except Exception as e:
                last_error = str(e)
                time.sleep(1)  # brief backoff before retry/fallback
                continue

    return {
        "success": False,
        "model_used": None,
        "text": None,
        "error": last_error,
    }
