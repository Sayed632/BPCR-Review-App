"""
ui/upload_view.py
Lets the user provide a BPCR page image either via file upload
or directly from their phone camera.
"""

import streamlit as st


def get_bpcr_page():
    st.subheader("Add BPCR Page")
    source = st.radio("Input method", ["Upload file", "Use camera"], horizontal=True)

    image_bytes = None

    if source == "Upload file":
        uploaded = st.file_uploader("Upload page image", type=["png", "jpg", "jpeg"])
        if uploaded:
            image_bytes = uploaded.getvalue()

    else:  # Use camera
        st.caption("Tip: hold phone parallel to the page, avoid glare and shadows.")
        captured = st.camera_input("Take a photo of the executed BPCR page")
        if captured:
            image_bytes = captured.getvalue()

    return image_bytes
