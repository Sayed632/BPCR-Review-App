"""
core/material_reconciler.py
Reconciles quantity indented vs. quantity actually used across all
operations that consumed a given material. Used qty should be equal to
or slightly less than indented (accounting for normal process loss).
"""


def _parse_qty(value: str):
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "")
    if cleaned.upper() in ("BLANK", "ILLEGIBLE", "NULL", ""):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def reconcile_materials(operations: list, materials_spec: list) -> dict:
    """
    operations: extraction results from extractor.extract_operations_from_page
                (each may include material_used + qty_used)
    materials_spec: the "materials" section of the master spec
                     [{material, qty_indented, unit, loss_tolerance_pct}]
    Returns:
      {
        "details": [ per-operation consumption rows ],
        "summary": [ per-material reconciliation rows ]
      }
    """
    spec_by_material = {m["material"]: m for m in materials_spec}

    details = []
    totals = {}

    for op in operations:
        material = op.get("material_used")
        if not material:
            continue

        qty = _parse_qty(op.get("qty_used"))
        details.append(
            {
                "material": material,
                "operation_id": op["operation_id"],
                "page_no": op["page_no"],
                "qty_used_raw": op.get("qty_used"),
                "qty_used_parsed": qty,
                "timestamp": op.get("timestamp"),
            }
        )

        if qty is not None:
            totals[material] = totals.get(material, 0) + qty

    summary = []
    for material, spec in spec_by_material.items():
        total_used = totals.get(material, 0)
        indented = spec["qty_indented"]
        tolerance_pct = spec.get("loss_tolerance_pct", 0)
        min_acceptable = indented * (1 - tolerance_pct / 100)

        if material not in totals:
            status = "NO_DATA"
        elif total_used > indented:
            status = "OVER_CONSUMED"
        elif total_used < min_acceptable:
            status = "EXCESS_LOSS"
        else:
            status = "RECONCILED"

        summary.append(
            {
                "material": material,
                "qty_indented": indented,
                "qty_used_total": round(total_used, 3) if material in totals else None,
                "unit": spec.get("unit", ""),
                "loss_tolerance_pct": tolerance_pct,
                "status": status,
            }
        )

    return {"details": details, "summary": summary}
