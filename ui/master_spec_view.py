"""
ui/master_spec_view.py
Upload + review flow for a Master BPCR. This always shows the raw
extracted JSON for editing before it's accepted as the active spec -
a misread spec value (e.g. a swapped tolerance) is a worse failure
mode than a misread executed value, since it silently changes what
"compliant" means for every batch reviewed against it afterwards.

Also supports a saved-spec library: once a spec is confirmed, it's
saved under a document number + version so future sessions can load
it directly instead of re-uploading and re-parsing the Master BPCR
every time.
"""

import json
import streamlit as st
from core.pdf_utils import is_pdf, pdf_to_page_images
from core.spec_parser import parse_master_bpcr, validate_spec
from core import storage


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


def _try_list_saved_specs():
    """Returns [] instead of crashing if the master_specs table doesn't
    exist yet or Supabase isn't configured - the spec library is a
    convenience, not a hard requirement to use the app."""
    try:
        return storage.list_master_specs()
    except Exception:
        return []


def _show_saved_spec_picker():
    saved_specs = _try_list_saved_specs()
    if not saved_specs:
        return

    st.caption("Or reuse a previously saved Master BPCR instead of re-uploading:")
    options = {
        f"{s['doc_number']} — v{s['version']} ({s.get('product_name', 'unnamed')})": s
        for s in saved_specs
    }
    choice = st.selectbox(
        "Load a saved spec", options=["-- none --"] + list(options.keys()), key="saved_spec_picker"
    )
    if choice != "-- none --" and st.button("Load Selected Spec"):
        picked = options[choice]
        try:
            spec = storage.load_master_spec(picked["doc_number"], picked["version"])
        except Exception as e:
            st.error(f"Could not load saved spec: {e}")
            return
        if spec:
            st.session_state["draft_spec_json"] = json.dumps(spec, indent=2)
            st.session_state["draft_spec_source"] = "loaded"
            st.session_state.pop("confirmed_spec", None)
            st.rerun()


def run_master_bpcr_parse_flow():
    """
    Full flow: [load saved OR upload -> parse] -> editable review ->
    confirm (with doc number/version, saved for future reuse).
    Returns the confirmed spec dict once the user accepts it, else None.
    """
    st.subheader("Step 1: Master BPCR")
    st.caption(
        "Upload the blank/template Master BPCR so the app knows what operations, "
        "materials, and parameters to check executed pages against."
    )

    _show_saved_spec_picker()

    files = get_master_bpcr_files()

    if files and st.button("Parse Master BPCR", type="primary"):
        page_images = files_to_page_images(files)
        if page_images:
            with st.spinner(f"Reading {len(page_images)} page(s) of the Master BPCR..."):
                draft_spec = parse_master_bpcr(page_images)
            st.session_state["draft_spec_json"] = json.dumps(draft_spec, indent=2)
            st.session_state["draft_spec_source"] = "parsed"
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

    source_label = "loaded from saved library" if st.session_state.get("draft_spec_source") == "loaded" else "freshly parsed"
    st.success(
        f"Draft spec ({source_label}): **{draft.get('product_name')}** — "
        f"{len(draft.get('personnel', []))} personnel, "
        f"{len(draft.get('materials', []))} materials, "
        f"{len(draft.get('operations', []))} operations. "
        "Review and correct before confirming."
    )

    with st.expander("Operations extracted (quick check)", expanded=(source_label == "freshly parsed")):
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

    st.markdown("**Save this spec for reuse** (skip re-upload/re-parse next time):")
    col_doc, col_ver = st.columns(2)
    with col_doc:
        doc_number = st.text_input(
            "Document Number",
            value=draft.get("_doc_number", ""),
            placeholder="e.g. BPCR-APPLE-ORANGE-001",
            key="doc_number_input",
        )
    with col_ver:
        version = st.text_input(
            "Version",
            value=draft.get("_version", "v1.0"),
            placeholder="e.g. v1.0",
            key="version_input",
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

            if not doc_number.strip() or not version.strip():
                st.error("Document Number and Version are required before confirming - "
                          "they're how this spec gets saved for reuse next time.")
                return None

            candidate["_doc_number"] = doc_number.strip()
            candidate["_version"] = version.strip()

            st.session_state["confirmed_spec"] = candidate
            st.session_state["draft_spec_json"] = json.dumps(candidate, indent=2)

            try:
                storage.save_master_spec(doc_number.strip(), version.strip(), candidate)
                st.success(
                    f"Spec confirmed and saved as **{doc_number} v{version}** - "
                    "it'll show up in \"Load a saved spec\" next time you don't want to re-upload."
                )
            except Exception as e:
                st.warning(
                    f"Spec confirmed for this session, but saving to the library failed "
                    f"({e}) - you'll need to re-upload next time. Check that the "
                    "master_specs table exists in Supabase."
                )

    with col2:
        if st.button("Discard Draft"):
            st.session_state.pop("draft_spec_json", None)
            st.session_state.pop("confirmed_spec", None)
            st.session_state.pop("draft_spec_source", None)
            st.rerun()

    return st.session_state.get("confirmed_spec")
