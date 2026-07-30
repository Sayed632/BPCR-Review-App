from core.timeseries_checker import check_timeseries

SPEC = {
    "table_name": "Table-1",
    "interval_minutes": 30,
    "interval_tolerance_minutes": 5,
    "value_unit": "degC",
    "spec_min": 85,
    "spec_max": 89,
}


def _row(date, time, value, recorded_by="A. Kumar"):
    return {"date": date, "time": time, "recorded_by": recorded_by, "value": value}


def test_all_in_range_no_missed_intervals():
    rows = [
        _row("12-03-2026", "10:00", "86"),
        _row("12-03-2026", "10:30", "87"),
        _row("12-03-2026", "11:00", "88"),
    ]
    result = check_timeseries(rows, SPEC, operation_id="OP-05")
    assert result["out_of_range"] == []
    assert result["missed_intervals"] == []


def test_out_of_range_flagged():
    rows = [_row("12-03-2026", "10:00", "95")]
    result = check_timeseries(rows, SPEC, operation_id="OP-05")
    assert len(result["out_of_range"]) == 1


def test_missed_interval_flagged():
    rows = [
        _row("12-03-2026", "10:00", "86"),
        _row("12-03-2026", "11:30", "87"),  # 90 min gap, way beyond 30+5
    ]
    result = check_timeseries(rows, SPEC, operation_id="OP-05")
    assert len(result["missed_intervals"]) == 1


def test_unparseable_row_flagged():
    rows = [_row("12-03-2026", "10:00", "ILLEGIBLE")]
    result = check_timeseries(rows, SPEC, operation_id="OP-05")
    assert len(result["unparseable_rows"]) == 1
