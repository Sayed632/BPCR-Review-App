"""
ui/master_spec_view.py
Upload + review flow for a Master BPCR. This always shows the raw
extracted JSON for editing before it's accepted as the active spec -
a misread spec value (e.g. a swapped tolerance) is a worse failure
mode than a misread executed value, since it silently changes what
"compliant" means for every batch reviewed against it afterwards.
"""

import json
import streamlit as st
from core.pdf_utils import is_pdf, pdf_to_page_images
from core.spec_parser import parse_master_bpcr, validate_spec


def get_master_bpcr_files():
    """Returns a list of (filename, bytes) tuples, or [] if nothing uploaded."""
    uploaded = st.file_uploader(
        "Upload Master BPCR (PDF or images, multiple pages/files allowed)",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="master_bpcr_uploader",
    )
    if not uploaded:
        return []
    return [(f.name, f.getvalue()) for f in uploaded]


def files_to_page_images(files: list[tuple[str, bytes]]) -> list[bytes]:
    """Expands any PDFs in the upload into per-page images, in upload order."""
    page_images = []
    for filename, file_bytes in files:
        if is_pdf(filename):
            try:
                page_images.extend(pdf_to_page_images(file_bytes))
            except ValueError as e:
                st.error(f"{filename}: {e}")
        else:
            page_images.append(file_bytes)
    return page_images


def run_master_bpcr_parse_flow():
    """
    Full flow: upload -> parse -> editable review -> confirm.
    Returns the confirmed spec dict once the user accepts it, else None.
    Uses st.session_state so the draft survives reruns while the user edits.
    """
    st.subheader("Step 1: Master BPCR")
    st.caption(
        "Upload the blank/template Master BPCR so the app knows what operations, "
        "materials, and parameters to check executed pages against."
    )

    files = get_master_bpcr_files()

    if files and st.button("Parse Master BPCR", type="primary"):
        page_images = files_to_page_images(files)
        if page_images:
            with st.spinner(f"Reading {len(page_images)} page(s) of the Master BPCR..."):
                draft_spec = parse_master_bpcr(page_images)
            st.session_state["draft_spec_json"] = json.dumps(draft_spec, indent=2)
            st.session_state.pop("confirmed_spec", None)

    if "draft_spec_json" not in st.session_state:
        return None

    draft = json.loads(st.session_state["draft_spec_json"])

    page_errors = draft.get("_page_errors") or []
    if page_errors:
        st.warning(
            f"{len(page_errors)} page(s) failed to parse and were skipped - "
            "review the JSON below and add anything missing by hand."
        )
        for err in page_errors:
            st.caption(f"Page {err['page']}: {err['error']}")

    st.success(
        f"Draft spec: **{draft.get('product_name')}** — "
        f"{len(draft.get('personnel', []))} personnel, "
        f"{len(draft.get('materials', []))} materials, "
        f"{len(draft.get('operations', []))} operations extracted. "
        "Review and correct before confirming."
    )

    with st.expander("Operations extracted (quick check)", expanded=True):
        for op in draft.get("operations", []):
            st.markdown(
                f"**{op.get('operation_id', '?')}** (page {op.get('page_no', '?')}): "
                f"{op.get('description', '(no description)')}"
            )

    edited_text = st.text_area(
        "Edit spec JSON directly if anything is wrong (wrong tolerance, missing "
        "operation, misread material name, etc.) before confirming:",
        value=st.session_state["draft_spec_json"],
        height=400,
        key="spec_json_editor",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Confirm & Use This Spec", type="primary"):
            try:
                candidate = json.loads(edited_text)
            except json.JSONDecodeError as e:
                st.error(f"That's not valid JSON: {e}")
                return None

            problems = validate_spec(candidate)
            if problems:
                st.error("Fix these before confirming:")
                for p in problems:
                    st.write(f"- {p}")
                return None

            st.session_state["confirmed_spec"] = candidate
            st.session_state["draft_spec_json"] = json.dumps(candidate, indent=2)
            st.success("Spec confirmed - proceed to upload executed BPCR pages below.")

    with col2:
        if st.button("Discard Draft"):
            st.session_state.pop("draft_spec_json", None)
            st.session_state.pop("confirmed_spec", None)
            st.rerun()

    return st.session_state.get("confirmed_spec")
