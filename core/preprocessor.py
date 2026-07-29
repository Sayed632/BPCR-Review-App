"""
core/preprocessor.py
Cleans up camera/scan images before they go to extraction.
Camera photos especially need this — glare, skew, and shadows
hurt handwriting recognition more than they hurt typed text.
"""

import cv2
import numpy as np
from PIL import Image
import io


def bytes_to_cv2(image_bytes: bytes):
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def cv2_to_bytes(cv2_img) -> bytes:
    success, buffer = cv2.imencode(".png", cv2_img)
    if not success:
        raise ValueError("Failed to encode image")
    return buffer.tobytes()


def deskew(cv2_img):
    gray = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) == 0:
        return cv2_img  # blank image, nothing to deskew

    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle

    (h, w) = cv2_img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        cv2_img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def enhance_contrast(cv2_img):
    lab = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2LAB)
    l_channel, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def preprocess_page(image_bytes: bytes) -> bytes:
    """
    Full preprocessing pipeline for one captured/uploaded page.
    Returns cleaned image bytes ready for extraction.
    """
    img = bytes_to_cv2(image_bytes)
    img = deskew(img)
    img = enhance_contrast(img)
    return cv2_to_bytes(img)
