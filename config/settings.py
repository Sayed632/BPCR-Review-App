"""
config/settings.py
Central place for constants and secret access.
Never hardcode keys here — always pull from st.secrets.
"""

import streamlit as st

def get_gemini_key() -> str:
    return st.secrets["GEMINI_API_KEY"]

# Paths
MASTER_SPECS_DIR = "data/master_specs"
SAMPLE_PAGES_DIR = "data/sample_pages"
OUTPUTS_DIR = "outputs"

# MVP default spec file (swap/select dynamically once multi-product support is added)
DEFAULT_SPEC_FILE = "sample_product_A.json"
