"""
core/comparator.py
Compares an extracted field value against its master spec entry.
MVP scope: numeric range check + simple text/vocabulary match.
Unit conversion and fuzzy text matching are post-MVP additions.
"""


def _parse_numeric(value: str):
    if value is None:
        return None
    cleaned = value.strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def evaluate_field(extraction_result: dict, spec: dict) -> dict:
    """
    extraction_result: output from extractor.extract_parameter_value()
    spec: the matching parameter entry from the master spec JSON
    Returns a row ready for the observation report.
    """
    written_value = extraction_result.get("written_value")
    status = "UNKNOWN"
    deviation_type = ""

    if not extraction_result.get("success") or written_value is None:
        status = "EXTRACTION_FAILED"
        deviation_type = extraction_result.get("error", "unknown error")

    elif written_value.upper() == "BLANK":
        status = "MISSING_ENTRY"

    elif written_value.upper() == "ILLEGIBLE":
        status = "ILLEGIBLE"

    elif spec["expected_type"] == "numeric":
        numeric_value = _parse_numeric(written_value)
        if numeric_value is None:
            status = "UNPARSEABLE"
            deviation_type = f"Could not parse '{written_value}' as a number"
        elif spec["spec_min"] <= numeric_value <= spec["spec_max"]:
            status = "IN_RANGE"
        else:
            status = "OUT_OF_RANGE"
            deviation_type = (
                f"{numeric_value} outside spec range "
                f"[{spec['spec_min']}-{spec['spec_max']}] {spec.get('unit', '')}"
            )

    elif spec["expected_type"] == "text":
        allowed = [v.upper() for v in spec.get("allowed_values", [])]
        if written_value.upper() in allowed:
            status = "IN_RANGE"
        else:
            status = "UNEXPECTED_VALUE"
            deviation_type = f"'{written_value}' not in allowed values {spec.get('allowed_values')}"

    return {
        "page_no": spec["page_no"],
        "parameter": spec["parameter"],
        "spec_instruction": (
            f"{spec['spec_min']}-{spec['spec_max']} {spec.get('unit', '')}"
            if spec["expected_type"] == "numeric"
            else f"Allowed: {spec.get('allowed_values')}"
        ),
        "written_value": written_value,
        "status": status,
        "deviation_type": deviation_type,
        "model_used": extraction_result.get("model_used"),
    }
