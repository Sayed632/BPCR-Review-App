from core.material_reconciler import reconcile_materials

MATERIALS_SPEC = [
    {"material": "APPLE", "type": "KSM", "qty_indented": 100, "unit": "kg",
     "tolerance_pct": 2, "tolerance_type": "two_sided"},
    {"material": "Orange", "type": "KSM", "qty_indented": 80, "unit": "kg",
     "tolerance_pct": 2, "tolerance_type": "two_sided",
     "conditional_addition": {"qty": 10, "unit": "kg", "related_operation": "OP-06"}},
    {"material": "IPA", "type": "GRM", "qty_indented": 500, "unit": "L",
     "tolerance_pct": 5, "tolerance_type": "two_sided"},
]


def _op(op_id, materials):
    return {"operation_id": op_id, "page_no": 1, "start_time": "01-01-2026 10:00", "materials": materials}


def test_two_sided_within_tolerance_upper():
    ops = [_op("OP-01", [{"material": "APPLE", "qty_used": "101.5"}])]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    apple = next(s for s in result["summary"] if s["material"] == "APPLE")
    assert apple["status"] == "RECONCILED"


def test_two_sided_over_consumed():
    ops = [_op("OP-01", [{"material": "APPLE", "qty_used": "105"}])]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    apple = next(s for s in result["summary"] if s["material"] == "APPLE")
    assert apple["status"] == "OVER_CONSUMED"


def test_conditional_addition_not_triggered_still_reconciled():
    # Orange charged at 70 (base), conditional +10 never happened - should
    # still reconcile since acceptable range accounts for the branch.
    ops = [_op("OP-03", [{"material": "Orange", "qty_used": "70"}])]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    orange = next(s for s in result["summary"] if s["material"] == "Orange")
    assert orange["status"] == "RECONCILED"


def test_conditional_addition_triggered_also_reconciled():
    ops = [
        _op("OP-03", [{"material": "Orange", "qty_used": "70"}]),
        _op("OP-06", [{"material": "Orange", "qty_used": "10"}]),
    ]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    orange = next(s for s in result["summary"] if s["material"] == "Orange")
    assert orange["status"] == "RECONCILED"
    assert orange["qty_used_total"] == 80


def test_excess_loss_below_conditional_floor():
    ops = [_op("OP-03", [{"material": "Orange", "qty_used": "50"}])]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    orange = next(s for s in result["summary"] if s["material"] == "Orange")
    assert orange["status"] == "EXCESS_LOSS"


def test_no_data():
    result = reconcile_materials([], MATERIALS_SPEC)
    ipa = next(s for s in result["summary"] if s["material"] == "IPA")
    assert ipa["status"] == "NO_DATA"


def test_multiple_materials_same_operation():
    ops = [_op("OP-03", [
        {"material": "APPLE", "qty_used": "100"},
        {"material": "Orange", "qty_used": "70"},
    ])]
    result = reconcile_materials(ops, MATERIALS_SPEC)
    assert len(result["details"]) == 2
