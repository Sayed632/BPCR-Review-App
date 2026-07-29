"""
app.py
BPCR Review App — MVP
Capture -> Preprocess -> Extract -> Compare -> Report
Operations persist to Supabase, keyed by batch number, so ALCOA checks
work across pages AND across sessions/days — not just within one run.
"""

import json
import streamlit as st

from config.settings import MASTER_SPECS_DIR, DEFAULT_SPEC_FILE
from core.preprocessor import preprocess_page
from core.extractor import extract_all_from_page, extract_operations_from_page
from core.comparator import evaluate_field
from core.report_builder import build_report_df
from core.chronology_checker import check_chronology
from core.material_reconciler import reconcile_materials
from core.storage import ensure_batch, save_operations, load_operations
from ui.upload_view import get_bpcr_page
from ui.review_view import show_report
from ui.alcoa_view import show_chronology, show_reconciliation

st.set_page_config(page_title="BPCR Review App", layout="wide")
st.title("BPCR Review App — MVP")
st.caption("Upload or photograph an executed BPCR page to review against spec.")


@st.cache_data
def load_spec(filename: str) -> dict:
    with open(f"{MASTER_SPECS_DIR}/{filename}") as f:
        return json.load(f)


spec = load_spec(DEFAULT_SPEC_FILE)
st.info(
    f"Loaded spec: **{spec['product_name']}** "
    f"({len(spec['parameters'])} parameters, {len(spec.get('operations', []))} operations)"
)

batch_number = st.text_input(
    "Batch Number",
    placeholder="e.g. B-2026-0142",
    help="Groups all pages/operations for this batch. Use the same batch "
    "number across sessions to keep building the same record.",
)

st.caption(
    "BPCRs span multiple pages. Process each page as you capture it — "
    "operations and ALCOA checks accumulate across pages and sessions "
    "for this batch number."
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

        with st.spinner("Reading handwritten values..."):
            extractions = extract_all_from_page(spec["parameters"], cleaned_bytes)
            operation_extractions = extract_operations_from_page(
                spec.get("operations", []), cleaned_bytes
            )

        with st.spinner("Comparing against spec..."):
            spec_by_name = {p["parameter"]: p for p in spec["parameters"]}
            evaluated_rows = [
                evaluate_field(extraction, spec_by_name[extraction["parameter"]])
                for extraction in extractions
            ]

        df = build_report_df(evaluated_rows)
        st.session_state["report_df"] = df

        with st.spinner("Saving to database..."):
            ensure_batch(batch_number, spec["product_name"], spec.get("bpcr_version"))
            # Only persist operations that actually have data on this page -
            # avoids overwriting a real reading from an earlier page with
            # this page's BLANK for the same operation_id.
            ops_with_data = [
                op
                for op in operation_extractions
                if op.get("operator") not in (None, "BLANK")
                or op.get("timestamp") not in (None, "BLANK")
            ]
            save_operations(batch_number, ops_with_data)

if "report_df" in st.session_state:
    show_report(st.session_state["report_df"])

all_ops = load_operations(batch_number)

if all_ops:
    st.divider()
    st.header("ALCOA Data Integrity Checks")
    st.caption(f"Based on {len(all_ops)} operation(s) saved for batch **{batch_number}**.")

    chronology_result = check_chronology(all_ops)
    show_chronology(chronology_result)

    if spec.get("materials"):
        reconciliation_result = reconcile_materials(all_ops, spec["materials"])
        show_reconciliation(reconciliation_result)
