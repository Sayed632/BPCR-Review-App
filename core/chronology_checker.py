"""
core/chronology_checker.py
ALCOA "Attributable" + "Contemporaneous" check:
Flags cases where the same operator is recorded performing two different
operations at the same (or overlapping) timestamp — physically impossible,
and a classic data-integrity red flag (backdating, copying, proxy signing).
"""

from datetime import datetime
from itertools import combinations

TIMESTAMP_FORMATS = [
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y %I:%M %p",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %I:%M %p",
    "%Y-%m-%d %H:%M",
    "%H:%M",
    "%I:%M %p",
]


def _parse_timestamp(raw: str):
    if not raw or raw.upper() in ("BLANK", "ILLEGIBLE"):
        return None
    raw = raw.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _normalize_operator(name: str) -> str:
    return name.strip().upper() if name else ""


def check_chronology(operations: list) -> dict:
    """
    operations: list of extraction results from extractor.extract_operations_from_page
    Returns:
      {
        "conflicts": [ ... same operator, overlapping/duplicate timestamps ... ],
        "unparseable": [ ... entries whose timestamp couldn't be read ... ]
      }
    """
    parsed_entries = []
    unparseable = []

    for op in operations:
        operator = _normalize_operator(op.get("operator"))
        raw_ts = op.get("timestamp")
        parsed_ts = _parse_timestamp(raw_ts)

        if not operator or operator in ("BLANK", "ILLEGIBLE"):
            continue  # can't attribute — separate concern from comparator's MISSING_ENTRY flag

        if parsed_ts is None:
            unparseable.append(
                {
                    "operation_id": op["operation_id"],
                    "operator": op.get("operator"),
                    "raw_timestamp": raw_ts,
                    "page_no": op["page_no"],
                }
            )
            continue

        parsed_entries.append(
            {
                "operation_id": op["operation_id"],
                "description": op.get("description"),
                "operator": operator,
                "operator_raw": op.get("operator"),
                "timestamp": parsed_ts,
                "page_no": op["page_no"],
            }
        )

    conflicts = []
    by_operator = {}
    for entry in parsed_entries:
        by_operator.setdefault(entry["operator"], []).append(entry)

    for operator, entries in by_operator.items():
        entries.sort(key=lambda e: e["timestamp"])
        for a, b in combinations(entries, 2):
            if a["operation_id"] == b["operation_id"]:
                continue
            if a["timestamp"] == b["timestamp"]:
                conflicts.append(
                    {
                        "operator": a["operator_raw"],
                        "operation_1": a["operation_id"],
                        "time_1": a["timestamp"].strftime("%Y-%m-%d %H:%M"),
                        "page_1": a["page_no"],
                        "operation_2": b["operation_id"],
                        "time_2": b["timestamp"].strftime("%Y-%m-%d %H:%M"),
                        "page_2": b["page_no"],
                        "conflict_type": "IDENTICAL_TIMESTAMP_DIFFERENT_OPERATIONS",
                    }
                )

    return {"conflicts": conflicts, "unparseable": unparseable}
