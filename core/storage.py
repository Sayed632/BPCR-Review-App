"""
core/storage.py
Persists batch/operation data to Supabase so ALCOA checks (chronology,
reconciliation) work across sessions and pages, not just within one
Streamlit run.
"""

import streamlit as st
from supabase import create_client


@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def ensure_batch(batch_number: str, product_name: str, spec_version: str = None):
    client = get_client()
    client.table("batches").upsert(
        {
            "batch_number": batch_number,
            "product_name": product_name,
            "spec_version": spec_version,
        },
        on_conflict="batch_number",
    ).execute()


def save_operations(batch_number: str, operations: list):
    """
    operations: list of dicts from extractor.extract_operations_from_page()
    Upserts on (batch_number, operation_id) so re-processing the same page
    updates rather than duplicates.
    """
    client = get_client()
    rows = [
        {
            "batch_number": batch_number,
            "operation_id": op["operation_id"],
            "description": op.get("description"),
            "page_no": op.get("page_no"),
            "operator": op.get("operator"),
            "timestamp_raw": op.get("timestamp"),
            "qty_used": op.get("qty_used"),
            "material_used": op.get("material_used"),
            "model_used": op.get("model_used"),
        }
        for op in operations
    ]
    if rows:
        client.table("operations").upsert(
            rows, on_conflict="batch_number,operation_id"
        ).execute()


def load_operations(batch_number: str) -> list:
    """Returns all persisted operations for a batch, in the same shape
    extractor.extract_operations_from_page() produces, so downstream
    chronology_checker / material_reconciler code needs no changes."""
    client = get_client()
    result = (
        client.table("operations")
        .select("*")
        .eq("batch_number", batch_number)
        .execute()
    )
    return [
        {
            "operation_id": row["operation_id"],
            "description": row.get("description"),
            "page_no": row.get("page_no"),
            "operator": row.get("operator"),
            "timestamp": row.get("timestamp_raw"),
            "qty_used": row.get("qty_used"),
            "material_used": row.get("material_used"),
            "model_used": row.get("model_used"),
        }
        for row in result.data
    ]


def load_operations_by_operator(operator: str) -> list:
    """Cross-batch query — needed for a true chronology check, since the
    same operator could (in theory) be recorded on two different batches
    at an overlapping time, which is just as much a red flag."""
    client = get_client()
    result = (
        client.table("operations").select("*").ilike("operator", f"%{operator}%").execute()
    )
    return result.data
