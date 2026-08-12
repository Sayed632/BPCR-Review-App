"""
app.py
BPCR Review App - real-case pipeline for multi-material, multi-step
batch records with conditional branches and repeating log tables.

Flow:
  1. Upload the Master BPCR (PDF or images) -> parsed into a spec ->
     human reviews/edits it -> confirms.
  2. Upload executed BPCR page(s) (PDF or images, one or many) ->
     each page is reviewed against the confirmed spec.
  3. ALCOA / chronology / material reconciliation / time-series checks
     run across everything saved for the batch so far.
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
from core.duration_calculator import compute_operation_durations
from core.storage import (
    ensure_batch,
    save_rich_operations,
    save_timeseries_readings,
    save_parameter_observations,
    load_rich_operations,
    load_timeseries_readings,
)
from ui.upload_view import get_bpcr_pages
from ui.master_spec_view import run_master_bpcr_parse_flow
from ui.alcoa_view import (
    show_chronology,
    show_reconciliation,
    show_personnel_check,
    show_timeseries_issues,
)
from ui.apqr_view import show_apqr_dashboard

DEMO_SPEC_FILE = "apple_orange_batch.json"

st.set_page_config(page_title="BPCR Review App", layout="wide")
st.title("BPCR Review App")

mode = st.sidebar.radio("Mode", ["Batch Review", "APQR / Trend Analysis"])


@st.cache_data
def load_demo_spec(filename: str) -> dict:
    with open(f"{MASTER_SPECS_DIR}/{filename}") as f:
        return json.load(f)


confirmed_spec = run_master_bpcr_parse_flow()
using_demo_spec = confirmed_spec is None

if using_demo_spec:
    st.info(
        "No Master BPCR confirmed yet - using the bundled demo spec below "
        "for now. Upload and confirm a Master BPCR above to review your "
        "own product instead."
    )
    spec = load_demo_spec(DEMO_SPEC_FILE)
else:
    spec = confirmed_spec

if mode == "APQR / Trend Analysis":
    show_apqr_dashboard(spec["product_name"])
    st.stop()

st.divider()
st.subheader("Step 2: Executed BPCR")
st.caption("Upload or photograph the executed (handwritten) BPCR to review against the spec above.")
st.info(
    f"Active spec: **{spec['product_name']}** "
    f"({len(spec['materials'])} materials, {len(spec['operations'])} operations)"
    + (" — demo spec" if using_demo_spec else "")
)

batch_number = st.text_input(
    "Batch Number",
    placeholder="e.g. B-2026-0142",
    help="Groups all pages/operations for this batch across sessions.",
)

if not batch_number:
    st.warning("Enter a batch number above to begin.")
    st.stop()

pages = get_bpcr_pages()

if pages:
    with st.expander(f"{len(pages)} page(s) queued", expanded=True):
        cols = st.columns(min(len(pages), 4))
        for i, (label, image_bytes) in enumerate(pages):
            with cols[i % len(cols)]:
                st.image(image_bytes, caption=label, width=200)

    if st.button("Run Review", type="primary"):
        all_param_rows = []
        total_failed_ops = 0
        all_error_messages = set()

        progress = st.progress(0.0, text="Starting...")

        for page_index, (label, image_bytes) in enumerate(pages):
            progress.progress(
                page_index / len(pages), text=f"Processing {label} ({page_index + 1}/{len(pages)})..."
            )

            cleaned_bytes = preprocess_page(image_bytes)
            rich_ops = extract_rich_operations_from_page(spec["operations"], cleaned_bytes)

            failed_ops = [op for op in rich_ops if not op.get("success", True)]
            total_failed_ops += len(failed_ops)
            for op in failed_ops:
                if op.get("error"):
                    all_error_messages.add(op["error"])

            ops_with_data = [
                op
                for op in rich_ops
                if op.get("operator") not in (None, "BLANK")
                or op.get("start_time") not in (None, "BLANK")
            ]

            ensure_batch(batch_number, spec["product_name"], spec.get("bpcr_version"))
            if ops_with_data:
                save_rich_operations(batch_number, ops_with_data)

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
                        "success": op.get("success", True),
                        "model_used": op.get("model_used"),
                        "error": op.get("error"),
                    }
                    param_spec = {
                        "page_no": op["page_no"],
                        "parameter": pname,
                        **spec_params_by_name[pname],
                    }
                    row = evaluate_field(extraction_result, param_spec)
                    row["operation_id"] = op["operation_id"]
                    all_param_rows.append(row)

            for spec_op in spec["operations"]:
                ts_spec = spec_op.get("time_series_log")
                if not ts_spec:
                    continue
                rows = extract_timeseries_from_page(
                    ts_spec["table_name"], ts_spec.get("value_unit", ""), cleaned_bytes
                )
                if rows:
                    save_timeseries_readings(
                        batch_number, spec_op["operation_id"], ts_spec["table_name"], rows, spec_op["page_no"]
                    )

        progress.progress(1.0, text="Done.")

        if total_failed_ops:
            st.error(
                f"Extraction call failed for {total_failed_ops} operation(s) across "
                f"{len(pages)} page(s). Results below reflect failed API calls, not "
                "empty handwriting. Check OPENROUTER_API_KEY in Secrets and your "
                "OpenRouter free-tier rate limits."
            )
            for msg in all_error_messages:
                st.code(msg)

        if all_param_rows:
            st.session_state["param_rows"] = all_param_rows
            save_parameter_observations(batch_number, all_param_rows)

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
    st.header("Operation Durations")
    st.caption(
        "Operations with their own start/end times show their own duration. "
        "A run of operations sharing no individual timestamps is bounded by "
        "the nearest known start (before the run) and end (after the run), "
        "and that group duration is shown for each — marked 'inferred'."
    )
    durations = compute_operation_durations(all_ops, spec["operations"])
    import pandas as pd
    duration_rows = [
        {
            "Operation": d["operation_id"],
            "Description": d["description"],
            "Duration": d["duration_label"],
            "Source": "Own timestamps" if d["duration_source"] == "own"
                      else ("Inferred from group" if d["duration_source"] == "inferred_from_set" else "Unavailable"),
            "Group": ", ".join(d["group_operations"]) if len(d["group_operations"]) > 1 else "",
        }
        for d in durations
    ]
    st.dataframe(pd.DataFrame(duration_rows), use_container_width=True)

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
