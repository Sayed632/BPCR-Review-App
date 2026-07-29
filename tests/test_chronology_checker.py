from core.chronology_checker import check_chronology


def _op(op_id, operator, timestamp, page_no=1):
    return {
        "operation_id": op_id,
        "description": op_id,
        "page_no": page_no,
        "material_used": None,
        "operator": operator,
        "timestamp": timestamp,
        "qty_used": None,
    }


def test_no_conflict_different_times():
    ops = [
        _op("OP-01", "A. Kumar", "12-03-2026 10:00"),
        _op("OP-02", "A. Kumar", "12-03-2026 11:00"),
    ]
    result = check_chronology(ops)
    assert result["conflicts"] == []


def test_conflict_same_operator_same_time():
    ops = [
        _op("OP-01", "A. Kumar", "12-03-2026 10:00"),
        _op("OP-02", "A. Kumar", "12-03-2026 10:00"),
    ]
    result = check_chronology(ops)
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["conflict_type"] == "IDENTICAL_TIMESTAMP_DIFFERENT_OPERATIONS"


def test_no_conflict_different_operators_same_time():
    ops = [
        _op("OP-01", "A. Kumar", "12-03-2026 10:00"),
        _op("OP-02", "B. Rao", "12-03-2026 10:00"),
    ]
    result = check_chronology(ops)
    assert result["conflicts"] == []


def test_unparseable_timestamp_flagged():
    ops = [_op("OP-01", "A. Kumar", "sometime in the morning")]
    result = check_chronology(ops)
    assert len(result["unparseable"]) == 1


def test_blank_operator_skipped():
    ops = [_op("OP-01", "BLANK", "12-03-2026 10:00")]
    result = check_chronology(ops)
    assert result["conflicts"] == []
    assert result["unparseable"] == []
