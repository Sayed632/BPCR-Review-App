"""
ui/upload_view.py
Lets the user provide executed BPCR pages either via file upload
(image or PDF, single or multi-page) or directly from their phone
camera.
"""

import streamlit as st
from core.pdf_utils import is_pdf, pdf_to_page_images


def get_bpcr_pages() -> list[tuple[str, bytes]]:
    """
    Returns a list of (page_label, image_bytes) tuples, in order.
    A single image upload/camera shot returns one tuple. A PDF (or
    several files at once) expands into one tuple per page, so a
    whole executed BPCR can be uploaded and processed in one pass
    instead of one page at a time.
    """
    st.subheader("Add BPCR Page(s)")
    source = st.radio("Input method", ["Upload file", "Use camera"], horizontal=True)

    pages: list[tuple[str, bytes]] = []

    if source == "Upload file":
        uploaded_files = st.file_uploader(
            "Upload page image(s) or a PDF of the executed BPCR",
            type=["png", "jpg", "jpeg", "pdf"],
            accept_multiple_files=True,
        )
        if uploaded_files:
            for f in uploaded_files:
                file_bytes = f.getvalue()
                if is_pdf(f.name):
                    try:
                        pdf_pages = pdf_to_page_images(file_bytes)
                    except ValueError as e:
                        st.error(f"{f.name}: {e}")
                        continue
                    for i, page_bytes in enumerate(pdf_pages):
                        pages.append((f"{f.name} - page {i + 1}", page_bytes))
                else:
                    pages.append((f.name, file_bytes))

    else:  # Use camera
        st.caption("Tip: hold phone parallel to the page, avoid glare and shadows.")
        captured = st.camera_input("Take a photo of the executed BPCR page")
        if captured:
            pages.append(("Camera capture", captured.getvalue()))

    return pages

