"""
core/chronology_checker.py
ALCOA "Attributable" + "Contemporaneous" check.

Updated for real BPCRs where operations have a start time AND an end
time (e.g. "maintain 3 hours"), not just one instant. A conflict now
means: the same operator has two DIFFERENT operations whose
[start, end] windows genuinely overlap - not just an identical single
timestamp, which would falsely flag every long-running step against
itself-adjacent short ones.
"""

from datetime import datetime, timedelta
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
    if not raw or str(raw).upper() in ("BLANK", "ILLEGIBLE", "NONE"):
        return None
    raw = str(raw).strip()
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
    operations: extraction results, each with operator, start_time,
                and optionally end_time (falls back to timestamp for
                backward compatibility with single-point entries).
    Returns: {"conflicts": [...], "unparseable": [...]}
    """
    parsed_entries = []
    unparseable = []

    for op in operations:
        operator = _normalize_operator(op.get("operator"))
        raw_start = op.get("start_time") or op.get("timestamp")
        raw_end = op.get("end_time")

        if not operator or operator in ("BLANK", "ILLEGIBLE"):
            continue

        start = _parse_timestamp(raw_start)
        if start is None:
            unparseable.append(
                {
                    "operation_id": op.get("operation_id"),
                    "operator": op.get("operator"),
                    "raw_timestamp": raw_start,
                    "page_no": op.get("page_no"),
                }
            )
            continue

        end = _parse_timestamp(raw_end) if raw_end else None
        if end is None or end <= start:
            # No usable end time - treat as a near-instant point so it
            # only conflicts on genuine overlap, not by default.
            end = start + timedelta(minutes=1)

        parsed_entries.append(
            {
                "operation_id": op.get("operation_id"),
                "description": op.get("description"),
                "operator": operator,
                "operator_raw": op.get("operator"),
                "start": start,
                "end": end,
                "page_no": op.get("page_no"),
            }
        )

    conflicts = []
    by_operator = {}
    for entry in parsed_entries:
        by_operator.setdefault(entry["operator"], []).append(entry)

    for operator, entries in by_operator.items():
        entries.sort(key=lambda e: e["start"])
        for a, b in combinations(entries, 2):
            if a["operation_id"] == b["operation_id"]:
                continue
            overlap = a["start"] < b["end"] and b["start"] < a["end"]
            if overlap:
                conflicts.append(
                    {
                        "operator": a["operator_raw"],
                        "operation_1": a["operation_id"],
                        "window_1": f"{a['start'].strftime('%Y-%m-%d %H:%M')} - {a['end'].strftime('%H:%M')}",
                        "page_1": a["page_no"],
                        "operation_2": b["operation_id"],
                        "window_2": f"{b['start'].strftime('%Y-%m-%d %H:%M')} - {b['end'].strftime('%H:%M')}",
                        "page_2": b["page_no"],
                        "conflict_type": "OVERLAPPING_WINDOW_DIFFERENT_OPERATIONS",
                    }
                )

    return {"conflicts": conflicts, "unparseable": unparseable}
