"""
app.py
BPCR Review App — MVP
Capture -> Preprocess -> Extract -> Compare -> Report
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

if "all_operations" not in st.session_state:
    st.session_state["all_operations"] = {}  # keyed by operation_id, accumulates across pages

st.caption(
    "BPCRs span multiple pages. Process each page as you capture it — "
    "operations and ALCOA checks accumulate across pages in this session."
)

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

        # Merge operation data into the cross-page accumulator.
        # Only overwrite an existing entry if this page actually had real data
        # for it (avoids a later page's BLANK wiping out an earlier real reading).
        for op in operation_extractions:
            op_id = op["operation_id"]
            has_data = op.get("operator") not in (None, "BLANK") or op.get(
                "timestamp"
            ) not in (None, "BLANK")
            if op_id not in st.session_state["all_operations"] or has_data:
                st.session_state["all_operations"][op_id] = op

if "report_df" in st.session_state:
    show_report(st.session_state["report_df"])

if st.session_state["all_operations"]:
    st.divider()
    st.header("ALCOA Data Integrity Checks")
    st.caption(
        f"Based on {len(st.session_state['all_operations'])} operation(s) "
        "captured so far this session."
    )

    all_ops = list(st.session_state["all_operations"].values())

    chronology_result = check_chronology(all_ops)
    show_chronology(chronology_result)

    if spec.get("materials"):
        reconciliation_result = reconcile_materials(all_ops, spec["materials"])
        show_reconciliation(reconciliation_result)
