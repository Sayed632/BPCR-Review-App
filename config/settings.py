"""
config/settings.py
Central place for constants and secret access.
Never hardcode keys here — always pull from st.secrets.
"""

import streamlit as st

# OPENROUTER_API_KEY is read directly from st.secrets in core/model_router.py

# Paths
MASTER_SPECS_DIR = "data/master_specs"
SAMPLE_PAGES_DIR = "data/sample_pages"
OUTPUTS_DIR = "outputs"

# MVP default spec file (swap/select dynamically once multi-product support is added)
DEFAULT_SPEC_FILE = "sample_product_A.json"
