"""
core/personnel_validator.py
Cross-checks handwritten operator names/initials against the known
Signature Table on the master BPCR - strengthens the "Attributable"
ALCOA pillar by flagging entries that don't match any authorized
person, rather than just trusting whatever transcribed.
"""

import difflib


def _normalize(name: str) -> str:
    return (name or "").strip().upper()


def validate_operator(raw_name: str, personnel: list) -> dict:
    """
    Returns a match result for a single handwritten operator entry.
    Uses close-match fuzzy comparison to tolerate initials vs full
    names, minor spelling/handwriting transcription variance.
    """
    normalized = _normalize(raw_name)

    if not normalized or normalized in ("BLANK", "ILLEGIBLE"):
        return {"raw_name": raw_name, "status": "MISSING", "matched_person": None}

    known_names = [_normalize(p["name"]) for p in personnel]

    if normalized in known_names:
        idx = known_names.index(normalized)
        return {
            "raw_name": raw_name,
            "status": "MATCHED",
            "matched_person": personnel[idx]["name"],
        }

    close = difflib.get_close_matches(normalized, known_names, n=1, cutoff=0.6)
    if close:
        idx = known_names.index(close[0])
        return {
            "raw_name": raw_name,
            "status": "FUZZY_MATCHED",
            "matched_person": personnel[idx]["name"],
        }

    return {"raw_name": raw_name, "status": "UNRECOGNIZED", "matched_person": None}


def validate_operations(operations: list, personnel: list) -> list:
    """
    Runs validate_operator across all extracted operations, returning
    one row per operation with its match result attached.
    """
    results = []
    for op in operations:
        match = validate_operator(op.get("operator"), personnel)
        results.append(
            {
                "operation_id": op.get("operation_id"),
                "page_no": op.get("page_no"),
                **match,
            }
        )
    return results
