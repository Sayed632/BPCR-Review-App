from core.comparator import evaluate_field

NUMERIC_SPEC = {
    "parameter": "Granulation Temperature",
    "page_no": 3,
    "unit": "degC",
    "expected_type": "numeric",
    "spec_min": 55,
    "spec_max": 65,
}

TEXT_SPEC = {
    "parameter": "Weight Variation Check",
    "page_no": 8,
    "unit": "text",
    "expected_type": "text",
    "allowed_values": ["Compliant", "Not Compliant"],
}


def _extraction(value, success=True):
    return {
        "parameter": NUMERIC_SPEC["parameter"],
        "page_no": 3,
        "written_value": value,
        "model_used": "google/gemini-2.5-pro",
        "success": success,
        "error": None,
    }


def test_in_range():
    row = evaluate_field(_extraction("60"), NUMERIC_SPEC)
    assert row["status"] == "IN_RANGE"


def test_out_of_range():
    row = evaluate_field(_extraction("70"), NUMERIC_SPEC)
    assert row["status"] == "OUT_OF_RANGE"


def test_blank():
    row = evaluate_field(_extraction("BLANK"), NUMERIC_SPEC)
    assert row["status"] == "MISSING_ENTRY"


def test_illegible():
    row = evaluate_field(_extraction("ILLEGIBLE"), NUMERIC_SPEC)
    assert row["status"] == "ILLEGIBLE"


def test_unparseable():
    row = evaluate_field(_extraction("abc"), NUMERIC_SPEC)
    assert row["status"] == "UNPARSEABLE"


def test_text_compliant():
    extraction = _extraction("Compliant")
    extraction["parameter"] = TEXT_SPEC["parameter"]
    row = evaluate_field(extraction, TEXT_SPEC)
    assert row["status"] == "IN_RANGE"


def test_text_unexpected():
    extraction = _extraction("Passed")
    extraction["parameter"] = TEXT_SPEC["parameter"]
    row = evaluate_field(extraction, TEXT_SPEC)
    assert row["status"] == "UNEXPECTED_VALUE"
