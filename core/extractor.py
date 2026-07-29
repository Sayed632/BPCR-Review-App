"""
core/extractor.py
Builds a handwriting-transcription prompt per parameter and
calls model_router to get a structured reading back.
"""

import json
from core.model_router import extract_field


def _build_prompt(parameter: str, unit: str, expected_type: str) -> str:
    if expected_type == "numeric":
        return (
            f"This is a cropped field from a pharmaceutical batch production "
            f"record. The field is labeled '{parameter}' and expects a numeric "
            f"value in unit '{unit}'. Transcribe only the handwritten numeric "
            f"value exactly as written. If illegible, respond with 'ILLEGIBLE'. "
            f"If the field appears blank, respond with 'BLANK'. "
            f"Respond with only the value, no extra words."
        )
    else:
        return (
            f"This is a cropped field from a pharmaceutical batch production "
            f"record. The field is labeled '{parameter}' and expects a short "
            f"handwritten text entry (e.g. 'Compliant' / 'Not Compliant'). "
            f"Transcribe exactly what is written. If illegible, respond with "
            f"'ILLEGIBLE'. If blank, respond with 'BLANK'. "
            f"Respond with only the value, no extra words."
        )


def extract_parameter_value(parameter: dict, image_bytes: bytes) -> dict:
    """
    parameter: one entry from the master spec JSON
    image_bytes: cropped field image (post-preprocessing)
    Returns: {parameter, page_no, written_value, model_used, success}
    """
    prompt = _build_prompt(
        parameter["parameter"], parameter.get("unit", ""), parameter["expected_type"]
    )
    result = extract_field(prompt, image_bytes)

    return {
        "parameter": parameter["parameter"],
        "page_no": parameter["page_no"],
        "written_value": result["text"].strip() if result["success"] else None,
        "model_used": result.get("model_used"),
        "success": result["success"],
        "error": result.get("error"),
    }


def _build_whole_page_prompt(parameters: list) -> str:
    param_list = "\n".join(
        f"- \"{p['parameter']}\" (page {p['page_no']}, unit: {p.get('unit', 'n/a')}, "
        f"type: {p['expected_type']})"
        for p in parameters
    )
    return (
        "This image is a page from an executed pharmaceutical batch production "
        "control record, filled in by hand. Find and transcribe the handwritten "
        "values for the following fields:\n\n"
        f"{param_list}\n\n"
        "Respond with ONLY a JSON array, one object per field, in this exact form:\n"
        '[{"parameter": "<name>", "written_value": "<value or BLANK or ILLEGIBLE>"}]\n'
        "No other text, no markdown code fences, just the raw JSON array. "
        "If a field is not visible on this page, still include it with value 'BLANK'."
    )


def extract_all_from_page(parameters: list, image_bytes: bytes) -> list:
    """
    MVP mode: one vision call for the whole page instead of per-field crops.
    parameters: list of spec entries relevant to this page
    Returns a list of {parameter, page_no, written_value, model_used, success}
    """
    prompt = _build_whole_page_prompt(parameters)
    result = extract_field(prompt, image_bytes)

    if not result["success"]:
        return [
            {
                "parameter": p["parameter"],
                "page_no": p["page_no"],
                "written_value": None,
                "model_used": None,
                "success": False,
                "error": result.get("error"),
            }
            for p in parameters
        ]

    raw_text = result["text"].strip()
    # Strip accidental markdown fences if the model adds them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return [
            {
                "parameter": p["parameter"],
                "page_no": p["page_no"],
                "written_value": None,
                "model_used": result.get("model_used"),
                "success": False,
                "error": f"Could not parse model JSON response: {raw_text[:200]}",
            }
            for p in parameters
        ]

    by_name = {item.get("parameter"): item.get("written_value") for item in parsed}

    return [
        {
            "parameter": p["parameter"],
            "page_no": p["page_no"],
            "written_value": by_name.get(p["parameter"], "BLANK"),
            "model_used": result.get("model_used"),
            "success": True,
            "error": None,
        }
        for p in parameters
    ]
