from core.material_reconciler import reconcile_materials

MATERIALS_SPEC = [
    {"material": "Chemical A", "qty_indented": 100, "unit": "kg", "loss_tolerance_pct": 2}
]


def _op(op_id, material, qty_used, page_no=1):
    return {
        "operation_id": op_id,
        "page_no": page_no,
        "material_used": material,
        "qty_used": qty_used,
        "timestamp": "12-03-2026 10:00",
    }


def test_reconciled_within_tolerance():
    ops = [_op("OP-01", "Chemical A", "40"), _op("OP-04", "Chemical A", "58")]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    summary = result["summary"][0]
    assert summary["qty_used_total"] == 98
    assert summary["status"] == "RECONCILED"


def test_over_consumed():
    ops = [_op("OP-01", "Chemical A", "60"), _op("OP-04", "Chemical A", "50")]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    assert result["summary"][0]["status"] == "OVER_CONSUMED"


def test_excess_loss():
    ops = [_op("OP-01", "Chemical A", "40"), _op("OP-04", "Chemical A", "40")]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    assert result["summary"][0]["status"] == "EXCESS_LOSS"


def test_no_data():
    result = reconcile_materials([], MATERIALS_SPEC)
    assert result["summary"][0]["status"] == "NO_DATA"


def test_unparseable_qty_ignored_in_total():
    ops = [_op("OP-01", "Chemical A", "ILLEGIBLE"), _op("OP-04", "Chemical A", "98")]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    assert result["summary"][0]["qty_used_total"] == 98
