"""
app.py
BPCR Review App — real-case pipeline for multi-material, multi-step
batch records with conditional branches and repeating log tables.
"""

import json
import streamlit as st

from config.settings import MASTER_SPECS_DIR
from core.preprocessor import preprocess_page
from core.extractor import extract_rich_operations_from_page, extract_timeseries_from_page
from core.comparator import evaluate_field
from core.chronology_checker import check_chronology
from core.material_reconciler import reconcile_materials
from core.timeseries_checker import check_timeseries
from core.personnel_validator import validate_operations
from core.storage import (
    ensure_batch,
    save_rich_operations,
    save_timeseries_readings,
    load_rich_operations,
    load_timeseries_readings,
)
from ui.upload_view import get_bpcr_page
from ui.alcoa_view import (
    show_chronology,
    show_reconciliation,
    show_personnel_check,
    show_timeseries_issues,
)

REAL_SPEC_FILE = "apple_orange_batch.json"

st.set_page_config(page_title="BPCR Review App", layout="wide")
st.title("BPCR Review App")
st.caption("Upload or photograph an executed BPCR page to review against spec.")


@st.cache_data
def load_spec(filename: str) -> dict:
    with open(f"{MASTER_SPECS_DIR}/{filename}") as f:
        return json.load(f)


spec = load_spec(REAL_SPEC_FILE)
st.info(
    f"Loaded spec: **{spec['product_name']}** "
    f"({len(spec['materials'])} materials, {len(spec['operations'])} operations)"
)

batch_number = st.text_input(
    "Batch Number",
    placeholder="e.g. B-2026-0142",
    help="Groups all pages/operations for this batch across sessions.",
)

if not batch_number:
    st.warning("Enter a batch number above to begin.")
    st.stop()

image_bytes = get_bpcr_page()

if image_bytes:
    st.image(image_bytes, caption="Captured page", width=400)

    if st.button("Run Review", type="primary"):
        with st.spinner("Preprocessing image..."):
            cleaned_bytes = preprocess_page(image_bytes)

        with st.spinner("Reading operations, materials, and parameters..."):
            rich_ops = extract_rich_operations_from_page(spec["operations"], cleaned_bytes)

        # Only persist operations that actually have data on this page
        ops_with_data = [
            op
            for op in rich_ops
            if op.get("operator") not in (None, "BLANK")
            or op.get("start_time") not in (None, "BLANK")
        ]

        with st.spinner("Saving to database..."):
            ensure_batch(batch_number, spec["product_name"], spec.get("bpcr_version"))
            save_rich_operations(batch_number, ops_with_data)

        # Embedded parameter comparison (per-operation, e.g. Reflux Temperature)
        param_rows = []
        for op in rich_ops:
            spec_op = next((o for o in spec["operations"] if o["operation_id"] == op["operation_id"]), None)
            if not spec_op:
                continue
            spec_params_by_name = {p["parameter"]: p for p in spec_op.get("parameters", [])}
            for extracted_param in op.get("parameters", []):
                pname = extracted_param.get("parameter")
                if pname not in spec_params_by_name:
                    continue
                extraction_result = {
                    "written_value": extracted_param.get("written_value"),
                    "success": True,
                }
                param_spec = {
                    "page_no": op["page_no"],
                    "parameter": pname,
                    **spec_params_by_name[pname],
                }
                param_rows.append(evaluate_field(extraction_result, param_spec))

        if param_rows:
            st.session_state["param_rows"] = param_rows

        # Time-series logs (Table-1 / Table-2), only for operations with a spec entry
        for spec_op in spec["operations"]:
            ts_spec = spec_op.get("time_series_log")
            if not ts_spec:
                continue
            with st.spinner(f"Reading {ts_spec['table_name']}..."):
                rows = extract_timeseries_from_page(
                    ts_spec["table_name"], ts_spec.get("value_unit", ""), cleaned_bytes
                )
            if rows:
                save_timeseries_readings(
                    batch_number, spec_op["operation_id"], ts_spec["table_name"], rows, spec_op["page_no"]
                )

if "param_rows" in st.session_state and st.session_state["param_rows"]:
    st.divider()
    st.header("Parameter Observations")
    import pandas as pd
    st.dataframe(pd.DataFrame(st.session_state["param_rows"]), use_container_width=True)

all_ops = load_rich_operations(batch_number)

if all_ops:
    st.divider()
    st.header("ALCOA Data Integrity Checks")
    st.caption(f"Based on {len(all_ops)} operation(s) saved for batch **{batch_number}**.")

    chronology_result = check_chronology(all_ops)
    show_chronology(chronology_result)

    reconciliation_result = reconcile_materials(all_ops, spec["materials"])
    show_reconciliation(reconciliation_result)

    personnel_results = validate_operations(all_ops, spec.get("personnel", []))
    show_personnel_check(personnel_results)

    st.divider()
    st.header("Time-Series Log Checks")
    for spec_op in spec["operations"]:
        ts_spec = spec_op.get("time_series_log")
        if not ts_spec:
            continue
        rows = load_timeseries_readings(batch_number, ts_spec["table_name"])
        if not rows:
            continue
        ts_result = check_timeseries(rows, ts_spec, operation_id=spec_op["operation_id"])
        show_timeseries_issues(spec_op["operation_id"], ts_spec["table_name"], ts_result)
