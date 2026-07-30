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


def _build_operations_prompt(operations: list) -> str:
    op_list = "\n".join(
        f"- Operation \"{op['operation_id']}\" ({op['description']}): "
        f"needs operator name/initials={op.get('requires_operator', True)}, "
        f"needs timestamp={op.get('requires_timestamp', True)}, "
        f"needs quantity used (unit: {op.get('qty_unit', 'n/a')})="
        f"{op.get('requires_qty', False)}"
        for op in operations
    )
    return (
        "This image is a page from an executed pharmaceutical batch production "
        "control record. For data-integrity review, extract the following for "
        "each operation listed below, if present on this page:\n\n"
        f"{op_list}\n\n"
        "For each operation, extract:\n"
        "- operator: the handwritten name/initials/signature of who performed it "
        "(or 'BLANK'/'ILLEGIBLE')\n"
        "- timestamp: the handwritten date and/or time recorded for that "
        "operation, transcribed exactly as written (e.g. '12-03-2026 10:00 AM'). "
        "Use 'BLANK' or 'ILLEGIBLE' if not readable.\n"
        "- qty_used: the handwritten quantity used, if this operation requires "
        "one, else null.\n\n"
        "Respond with ONLY a JSON array, one object per operation, in this exact "
        "form:\n"
        '[{"operation_id": "OP-01", "operator": "<value>", "timestamp": "<value>", '
        '"qty_used": "<value or null>"}]\n'
        "No other text, no markdown code fences, just the raw JSON array. If an "
        "operation is not visible on this page, still include it with 'BLANK' "
        "values."
    )


def extract_operations_from_page(operations: list, image_bytes: bytes) -> list:
    """
    Extracts operator, timestamp, and quantity-used data per operation from
    one page, for ALCOA chronology and material reconciliation checks.
    """
    prompt = _build_operations_prompt(operations)
    result = extract_field(prompt, image_bytes)

    if not result["success"]:
        return [
            {
                "operation_id": op["operation_id"],
                "description": op["description"],
                "page_no": op["page_no"],
                "material_used": op.get("material_used"),
                "operator": None,
                "timestamp": None,
                "qty_used": None,
                "model_used": None,
                "success": False,
                "error": result.get("error"),
            }
            for op in operations
        ]

    raw_text = result["text"].strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`").replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return [
            {
                "operation_id": op["operation_id"],
                "description": op["description"],
                "page_no": op["page_no"],
                "material_used": op.get("material_used"),
                "operator": None,
                "timestamp": None,
                "qty_used": None,
                "model_used": result.get("model_used"),
                "success": False,
                "error": f"Could not parse model JSON response: {raw_text[:200]}",
            }
            for op in operations
        ]

    by_id = {item.get("operation_id"): item for item in parsed}

    output = []
    for op in operations:
        item = by_id.get(op["operation_id"], {})
        output.append(
            {
                "operation_id": op["operation_id"],
                "description": op["description"],
                "page_no": op["page_no"],
                "material_used": op.get("material_used"),
                "operator": item.get("operator", "BLANK"),
                "timestamp": item.get("timestamp", "BLANK"),
                "qty_used": item.get("qty_used"),
                "model_used": result.get("model_used"),
                "success": True,
                "error": None,
            }
        )
    return output


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


def _build_rich_operations_prompt(operations: list) -> str:
    op_blocks = []
    for op in operations:
        materials = op.get("materials_used", [])
        mat_desc = (
            ", ".join(f"{m['material']} (unit: {m.get('unit', 'n/a')})" for m in materials)
            if materials
            else "none"
        )
        params = op.get("parameters", [])
        param_desc = (
            ", ".join(f"{p['parameter']} (unit: {p.get('unit', 'n/a')})" for p in params)
            if params
            else "none"
        )
        op_blocks.append(
            f"- Operation \"{op['operation_id']}\" ({op['description']}): "
            f"operator required={op.get('requires_operator', True)}, "
            f"start_time required={op.get('requires_start_time', True)}, "
            f"end_time required={op.get('requires_end_time', False)}, "
            f"materials to read quantity for: {mat_desc}, "
            f"parameters to read: {param_desc}"
        )
    op_list = "\n".join(op_blocks)

    return (
        "This image is a page from an executed pharmaceutical batch production "
        "control record. For each operation below, extract what is visible on "
        "this page:\n\n"
        f"{op_list}\n\n"
        "For each operation return:\n"
        "- operator: handwritten name/initials/signature ('BLANK' or 'ILLEGIBLE' if not readable)\n"
        "- start_time: handwritten start date/time, exactly as written\n"
        "- end_time: handwritten end date/time, exactly as written (if applicable)\n"
        "- materials: array of {\"material\": name, \"qty_used\": value} for each "
        "material listed for that operation\n"
        "- parameters: array of {\"parameter\": name, \"written_value\": value} for "
        "each parameter listed for that operation\n\n"
        "Respond with ONLY a JSON array, one object per operation:\n"
        '[{"operation_id": "OP-01", "operator": "<value>", "start_time": "<value>", '
        '"end_time": "<value or null>", "materials": [...], "parameters": [...]}]\n'
        "No other text, no markdown fences. Use 'BLANK' for anything not visible "
        "on this page, still include every operation listed above."
    )


def extract_rich_operations_from_page(operations: list, image_bytes: bytes) -> list:
    """
    Extended extraction: operator, start/end time, multiple materials,
    and embedded parameters per operation - matches the real BPCR schema
    (materials_used list, requires_start_time/end_time, parameters).
    """
    prompt = _build_rich_operations_prompt(operations)
    result = extract_field(prompt, image_bytes)

    def _blank_row(op):
        return {
            "operation_id": op["operation_id"],
            "description": op["description"],
            "page_no": op["page_no"],
            "operator": "BLANK",
            "start_time": "BLANK",
            "end_time": None,
            "materials": [{"material": m["material"], "qty_used": "BLANK"} for m in op.get("materials_used", [])],
            "parameters": [{"parameter": p["parameter"], "written_value": "BLANK"} for p in op.get("parameters", [])],
            "model_used": result.get("model_used"),
            "success": result["success"],
            "error": result.get("error"),
        }

    if not result["success"]:
        return [_blank_row(op) for op in operations]

    raw_text = result["text"].strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`").replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        rows = [_blank_row(op) for op in operations]
        for row in rows:
            row["success"] = False
            row["error"] = f"Could not parse model JSON response: {raw_text[:200]}"
        return rows

    by_id = {item.get("operation_id"): item for item in parsed}

    output = []
    for op in operations:
        item = by_id.get(op["operation_id"], {})
        output.append(
            {
                "operation_id": op["operation_id"],
                "description": op["description"],
                "page_no": op["page_no"],
                "operator": item.get("operator", "BLANK"),
                "start_time": item.get("start_time", "BLANK"),
                "end_time": item.get("end_time"),
                "materials": item.get("materials", []),
                "parameters": item.get("parameters", []),
                "model_used": result.get("model_used"),
                "success": True,
                "error": None,
            }
        )
    return output


def _build_timeseries_prompt(table_name: str, value_unit: str) -> str:
    return (
        f"This image is a page from an executed pharmaceutical batch production "
        f"control record. Find the handwritten log table titled '{table_name}' "
        f"which records periodic readings with columns: Date, Time, Recorded By "
        f"(operator), and a value in unit '{value_unit}'. Transcribe every row "
        f"you can see.\n\n"
        "Respond with ONLY a JSON array, one object per row:\n"
        '[{"date": "<value>", "time": "<value>", "recorded_by": "<value>", '
        '"value": "<value>"}]\n'
        "If the table is not visible on this page, respond with an empty JSON "
        "array []. No other text, no markdown fences."
    )


def extract_timeseries_from_page(table_name: str, value_unit: str, image_bytes: bytes) -> list:
    """
    Extracts rows from a repeating log table (e.g. Table-1/Table-2 hourly
    temperature readings) on one page.
    """
    prompt = _build_timeseries_prompt(table_name, value_unit)
    result = extract_field(prompt, image_bytes)

    if not result["success"]:
        return []

    raw_text = result["text"].strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`").replace("json", "", 1).strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return []
