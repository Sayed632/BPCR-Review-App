"""
core/pdf_utils.py
Renders each page of an uploaded PDF into PNG image bytes, so PDF uploads
(Master BPCR or executed/handwritten BPCR) can flow through the same
vision-extraction pipeline as a photographed/scanned image page.

Uses PyMuPDF (import name "fitz") specifically because it's a
self-contained wheel with its own PDF rendering - no system-level
poppler/ghostscript install needed on Streamlit Cloud, unlike
pdf2image.
"""

import fitz  # PyMuPDF

RENDER_DPI = 200  # good balance of handwriting legibility vs. file size/upload cost


def is_pdf(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def pdf_to_page_images(pdf_bytes: bytes) -> list[bytes]:
    """
    Returns a list of PNG image bytes, one per page, in page order.
    Raises ValueError with a clean message if the PDF can't be opened
    (corrupt file, password-protected, etc) - never leaks a raw
    exception straight to the UI.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        raise ValueError(
            "Could not open this PDF - it may be corrupted, empty, or password-protected."
        )

    if doc.needs_pass:
        doc.close()
        raise ValueError("This PDF is password-protected. Please upload an unlocked copy.")

    if doc.page_count == 0:
        doc.close()
        raise ValueError("This PDF has no pages.")

    zoom = RENDER_DPI / 72  # PDF base unit is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)

    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        images.append(pix.tobytes("png"))

    doc.close()
    return images
