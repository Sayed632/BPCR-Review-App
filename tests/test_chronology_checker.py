from core.chronology_checker import check_chronology


def _op(op_id, operator, start, end=None, page_no=1):
    return {
        "operation_id": op_id,
        "description": op_id,
        "page_no": page_no,
        "operator": operator,
        "start_time": start,
        "end_time": end,
    }


def test_no_overlap_sequential():
    ops = [
        _op("OP-01", "A. Kumar", "12-03-2026 10:00", "12-03-2026 10:30"),
        _op("OP-02", "A. Kumar", "12-03-2026 10:30", "12-03-2026 11:00"),
    ]
    # touching boundary, not overlapping
    result = check_chronology(ops)
    assert result["conflicts"] == []


def test_overlapping_windows_same_operator():
    ops = [
        _op("OP-01", "A. Kumar", "12-03-2026 10:00", "12-03-2026 11:00"),
        _op("OP-02", "A. Kumar", "12-03-2026 10:30", "12-03-2026 10:45"),
    ]
    result = check_chronology(ops)
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["conflict_type"] == "OVERLAPPING_WINDOW_DIFFERENT_OPERATIONS"


def test_no_overlap_different_operators():
    ops = [
        _op("OP-01", "A. Kumar", "12-03-2026 10:00", "12-03-2026 11:00"),
        _op("OP-02", "B. Rao", "12-03-2026 10:30", "12-03-2026 10:45"),
    ]
    result = check_chronology(ops)
    assert result["conflicts"] == []


def test_missing_end_time_falls_back_to_point():
    ops = [
        _op("OP-01", "A. Kumar", "12-03-2026 10:00"),
        _op("OP-02", "A. Kumar", "12-03-2026 10:00"),
    ]
    result = check_chronology(ops)
    assert len(result["conflicts"]) == 1


def test_unparseable_start_time_flagged():
    ops = [_op("OP-01", "A. Kumar", "sometime")]
    result = check_chronology(ops)
    assert len(result["unparseable"]) == 1
