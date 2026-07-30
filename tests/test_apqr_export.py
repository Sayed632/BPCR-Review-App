from unittest.mock import patch
import core.apqr_export as apqr_export


PARAM_OBS = [
    {"batch_number": "B-001", "parameter": "Reflux Temperature", "written_value": "87",
     "status": "IN_RANGE", "spec_instruction": "85-90 degC", "deviation_type": "", "created_at": "2026-01-01"},
    {"batch_number": "B-001", "parameter": "RPM Maintained", "written_value": "20",
     "status": "OUT_OF_RANGE", "spec_instruction": "5-15 rpm", "deviation_type": "too high", "created_at": "2026-01-01"},
    {"batch_number": "B-002", "parameter": "Reflux Temperature", "written_value": "88",
     "status": "IN_RANGE", "spec_instruction": "85-90 degC", "deviation_type": "", "created_at": "2026-02-01"},
]

MATERIAL_ROWS = [
    {"batch_number": "B-001", "material": "APPLE", "qty_used_raw": "100"},
    {"batch_number": "B-001", "material": "APPLE", "qty_used_raw": "0"},
    {"batch_number": "B-002", "material": "APPLE", "qty_used_raw": "98"},
]

BATCHES = [
    {"batch_number": "B-001", "product_name": "Test Product", "spec_version": "v1", "created_at": "2026-01-01"},
    {"batch_number": "B-002", "product_name": "Test Product", "spec_version": "v1", "created_at": "2026-02-01"},
]


def test_parameter_trend_table():
    with patch.object(apqr_export, "load_all_parameter_observations", return_value=PARAM_OBS):
        df = apqr_export.build_parameter_trend_table("Test Product")
    assert len(df) == 3
    assert "Reflux Temperature" in df["parameter"].values


def test_parameter_pivot_table():
    with patch.object(apqr_export, "load_all_parameter_observations", return_value=PARAM_OBS):
        pivot = apqr_export.build_parameter_pivot_table("Test Product")
    assert "Reflux Temperature" in pivot.columns
    assert len(pivot) == 2  # two batches


def test_deviation_rate_table():
    with patch.object(apqr_export, "load_all_parameter_observations", return_value=PARAM_OBS):
        dev_df = apqr_export.build_deviation_rate_table("Test Product")
    b001 = dev_df[dev_df["batch_number"] == "B-001"].iloc[0]
    assert b001["out_of_range"] == 1
    assert b001["in_range"] == 1


def test_material_usage_trend():
    with patch.object(apqr_export, "load_all_operation_materials", return_value=MATERIAL_ROWS):
        df = apqr_export.build_material_usage_trend("Test Product")
    b001_total = df[(df["batch_number"] == "B-001") & (df["material"] == "APPLE")]["qty_used_total"].iloc[0]
    assert b001_total == 100


def test_empty_data_returns_empty_frame():
    with patch.object(apqr_export, "load_all_parameter_observations", return_value=[]):
        df = apqr_export.build_parameter_trend_table("Test Product")
    assert df.empty


def test_batch_list():
    with patch.object(apqr_export, "load_all_batches", return_value=BATCHES):
        df = apqr_export.build_batch_list("Test Product")
    assert len(df) == 2
