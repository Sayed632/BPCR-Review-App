"""
core/material_reconciler.py
Reconciles quantity indented vs. quantity actually used across all
operations that consumed a given material.

Real-world rules this now supports:
- Type-based, two-sided tolerance (e.g. KSM +-2%, GRM +-5%, per Note 1/2
  on the master BPCR) instead of a single global "loss only" tolerance.
- Multiple materials consumed within a single operation.
- Conditional material additions (e.g. Orange +10 kg only if an IPC
  result triggers it) - modeled as a widened acceptable range rather
  than a single fixed target, since the "correct" total legitimately
  depends on a branch that isn't known until the batch is reviewed.
"""


def _parse_qty(value):
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "")
    if cleaned.upper() in ("BLANK", "ILLEGIBLE", "NULL", ""):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _acceptable_range(spec: dict) -> tuple:
    """
    Returns (min_acceptable, max_acceptable) for a material, accounting
    for tolerance type and any conditional addition.
    """
    indented = spec["qty_indented"]
    tol_pct = spec.get("tolerance_pct", 0)
    tol_type = spec.get("tolerance_type", "loss_only")

    conditional = spec.get("conditional_addition")
    base_min = indented - conditional["qty"] if conditional else indented

    if tol_type == "two_sided":
        min_acceptable = base_min * (1 - tol_pct / 100)
        max_acceptable = indented * (1 + tol_pct / 100)
    else:  # loss_only - used stays at or below indented, within tolerance loss
        min_acceptable = base_min * (1 - tol_pct / 100)
        max_acceptable = indented

    return (min_acceptable, max_acceptable)


def reconcile_materials(operations: list, materials_spec: list) -> dict:
    """
    operations: extraction results, each optionally containing a
                "materials" list: [{"material": name, "qty_used": raw}, ...]
    materials_spec: the "materials" section of the master spec
    Returns: {"details": [...], "summary": [...]}
    """
    spec_by_material = {m["material"]: m for m in materials_spec}

    details = []
    totals = {}

    for op in operations:
        for mat_entry in op.get("materials", []):
            material = mat_entry.get("material")
            if not material:
                continue
            qty = _parse_qty(mat_entry.get("qty_used"))
            details.append(
                {
                    "material": material,
                    "operation_id": op.get("operation_id"),
                    "page_no": op.get("page_no"),
                    "qty_used_raw": mat_entry.get("qty_used"),
                    "qty_used_parsed": qty,
                    "timestamp": op.get("start_time") or op.get("timestamp"),
                }
            )
            if qty is not None:
                totals[material] = totals.get(material, 0) + qty

    summary = []
    for material, spec in spec_by_material.items():
        total_used = totals.get(material, 0)
        min_acceptable, max_acceptable = _acceptable_range(spec)

        if material not in totals:
            status = "NO_DATA"
        elif total_used > max_acceptable:
            status = "OVER_CONSUMED"
        elif total_used < min_acceptable:
            status = "EXCESS_LOSS"
        else:
            status = "RECONCILED"

        summary.append(
            {
                "material": material,
                "type": spec.get("type"),
                "qty_indented": spec["qty_indented"],
                "qty_used_total": round(total_used, 3) if material in totals else None,
                "unit": spec.get("unit", ""),
                "tolerance_pct": spec.get("tolerance_pct", 0),
                "tolerance_type": spec.get("tolerance_type", "loss_only"),
                "acceptable_range": f"{round(min_acceptable, 2)}-{round(max_acceptable, 2)}",
                "status": status,
            }
        )

    return {"details": details, "summary": summary}
