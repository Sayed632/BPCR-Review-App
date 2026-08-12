"""
core/duration_calculator.py
Computes how long each operation took.

Most operations have their own start_time and end_time - duration is
just the difference. But some real BPCRs group several sub-steps
under one shared start/end window (e.g. steps 6-8 in a distillation
sequence might only have a start time on step 6 and an end time on
step 8, with nothing recorded in between). For any run of consecutive
operations (in spec order) that are individually missing a usable
start and/or end, this treats them as one set and computes duration
as (nearest known end time at or after the set) - (nearest known
start time at or before the set), then reports that same window for
every operation in the set, clearly marked as inferred rather than
its own.
"""

from core.chronology_checker import parse_timestamp


def _get_description(op_id: str, actual_by_id: dict, spec_by_id: dict) -> str:
    if op_id in actual_by_id and actual_by_id[op_id].get("description"):
        return actual_by_id[op_id]["description"]
    if op_id in spec_by_id:
        return spec_by_id[op_id].get("description", "")
    return ""


def format_duration(minutes: float | None) -> str:
    if minutes is None:
        return "Unavailable"
    if minutes < 0:
        return "Invalid (end before start)"
    hours, mins = divmod(round(minutes), 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def compute_operation_durations(all_ops: list, spec_operations: list) -> list:
    """
    all_ops: rows from storage.load_rich_operations() - each has
             operation_id, start_time, end_time (raw strings).
    spec_operations: spec["operations"] - defines the canonical
             sequence order and provides descriptions/fallback info
             for operations that have no extracted data at all.
    Returns one row per spec operation:
        {operation_id, description, duration_minutes, duration_label,
         duration_source: "own" | "inferred_from_set" | "unavailable",
         group_operations: [ids in the same inferred set, including self],
         start_used, end_used}
    """
    actual_by_id = {op["operation_id"]: op for op in all_ops}
    spec_by_id = {op["operation_id"]: op for op in spec_operations}
    ordered_ids = [op["operation_id"] for op in spec_operations]

    parsed = []
    for op_id in ordered_ids:
        actual = actual_by_id.get(op_id, {})
        parsed.append(
            {
                "operation_id": op_id,
                "description": _get_description(op_id, actual_by_id, spec_by_id),
                "start": parse_timestamp(actual.get("start_time")),
                "end": parse_timestamp(actual.get("end_time")),
            }
        )

    results = []
    n = len(parsed)
    i = 0
    while i < n:
        cur = parsed[i]

        # Case 1: this operation has its own complete, valid window.
        if cur["start"] is not None and cur["end"] is not None and cur["end"] >= cur["start"]:
            duration_minutes = (cur["end"] - cur["start"]).total_seconds() / 60
            results.append(
                {
                    "operation_id": cur["operation_id"],
                    "description": cur["description"],
                    "duration_minutes": duration_minutes,
                    "duration_label": format_duration(duration_minutes),
                    "duration_source": "own",
                    "group_operations": [cur["operation_id"]],
                    "start_used": cur["start"],
                    "end_used": cur["end"],
                }
            )
            i += 1
            continue

        # Case 2: missing (or invalid) timing - collect the run of
        # consecutive operations that are each individually incomplete,
        # then bound the whole run with the nearest known times outside it.
        group = [cur]
        j = i + 1
        while j < n:
            nxt = parsed[j]
            if nxt["start"] is not None and nxt["end"] is not None and nxt["end"] >= nxt["start"]:
                break
            group.append(nxt)
            j += 1

        anchor_start = cur["start"]  # this op's own start, if it has one but no end
        if anchor_start is None:
            for k in range(i - 1, -1, -1):
                candidate = parsed[k]["end"] or parsed[k]["start"]
                if candidate is not None:
                    anchor_start = candidate
                    break

        last_in_group = group[-1]
        anchor_end = last_in_group["end"] or last_in_group["start"]
        if anchor_end is None:
            for k in range(j, n):
                candidate = parsed[k]["start"] or parsed[k]["end"]
                if candidate is not None:
                    anchor_end = candidate
                    break

        if anchor_start is not None and anchor_end is not None and anchor_end >= anchor_start:
            duration_minutes = (anchor_end - anchor_start).total_seconds() / 60
            source = "own" if len(group) == 1 and cur["start"] and cur["end"] else "inferred_from_set"
        else:
            duration_minutes = None
            source = "unavailable"

        group_ids = [g["operation_id"] for g in group]
        for g in group:
            results.append(
                {
                    "operation_id": g["operation_id"],
                    "description": g["description"],
                    "duration_minutes": duration_minutes,
                    "duration_label": format_duration(duration_minutes),
                    "duration_source": source,
                    "group_operations": group_ids,
                    "start_used": anchor_start,
                    "end_used": anchor_end,
                }
            )
        i = j

    return results
