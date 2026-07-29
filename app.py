"""
app.py
BPCR Review App — MVP
Capture -> Preprocess -> Extract -> Compare -> Report
"""

import json
import streamlit as st

from config.settings import MASTER_SPECS_DIR, DEFAULT_SPEC_FILE
from core.preprocessor import preprocess_page
from core.extractor import extract_all_from_page
from core.comparator import evaluate_field
from core.report_builder import build_report_df
from ui.upload_view import get_bpcr_page
from ui.review_view import show_report

st.set_page_config(page_title="BPCR Review App", layout="wide")
st.title("BPCR Review App — MVP")
st.caption("Upload or photograph an executed BPCR page to review against spec.")


@st.cache_data
def load_spec(filename: str) -> dict:
    with open(f"{MASTER_SPECS_DIR}/{filename}") as f:
        return json.load(f)


spec = load_spec(DEFAULT_SPEC_FILE)
st.info(f"Loaded spec: **{spec['product_name']}** ({len(spec['parameters'])} parameters)")

image_bytes = get_bpcr_page()

if image_bytes:
    st.image(image_bytes, caption="Captured page", width=400)

    if st.button("Run Review", type="primary"):
        with st.spinner("Preprocessing image..."):
            cleaned_bytes = preprocess_page(image_bytes)

        with st.spinner("Reading handwritten values..."):
            extractions = extract_all_from_page(spec["parameters"], cleaned_bytes)

        with st.spinner("Comparing against spec..."):
            spec_by_name = {p["parameter"]: p for p in spec["parameters"]}
            evaluated_rows = [
                evaluate_field(extraction, spec_by_name[extraction["parameter"]])
                for extraction in extractions
            ]

        df = build_report_df(evaluated_rows)
        st.session_state["report_df"] = df

if "report_df" in st.session_state:
    show_report(st.session_state["report_df"])
