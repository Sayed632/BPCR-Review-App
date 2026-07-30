"""
core/storage.py
Persists batch/operation data to Supabase so ALCOA checks (chronology,
reconciliation, time-series) work across sessions and pages.
Updated for the real-BPCR schema: multiple materials per operation,
start/end time windows, and repeating time-series log rows.
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
        {"batch_number": batch_number, "product_name": product_name, "spec_version": spec_version},
        on_conflict="batch_number",
    ).execute()


def save_rich_operations(batch_number: str, operations: list):
    """
    operations: list from extractor.extract_rich_operations_from_page()
    Saves operator/start/end to `operations`, and each material reading
    to `operation_materials`.
    """
    client = get_client()

    op_rows = [
        {
            "batch_number": batch_number,
            "operation_id": op["operation_id"],
            "description": op.get("description"),
            "page_no": op.get("page_no"),
            "operator": op.get("operator"),
            "start_time_raw": op.get("start_time"),
            "end_time_raw": op.get("end_time"),
            "model_used": op.get("model_used"),
        }
        for op in operations
    ]
    if op_rows:
        client.table("operations").upsert(op_rows, on_conflict="batch_number,operation_id").execute()

    material_rows = []
    for op in operations:
        for mat in op.get("materials", []):
            if mat.get("qty_used") in (None, "BLANK"):
                continue
            material_rows.append(
                {
                    "batch_number": batch_number,
                    "operation_id": op["operation_id"],
                    "material": mat["material"],
                    "qty_used_raw": mat.get("qty_used"),
                    "page_no": op.get("page_no"),
                }
            )
    if material_rows:
        client.table("operation_materials").upsert(
            material_rows, on_conflict="batch_number,operation_id,material"
        ).execute()


def save_timeseries_readings(batch_number: str, operation_id: str, table_name: str, rows: list, page_no: int = None):
    client = get_client()
    db_rows = [
        {
            "batch_number": batch_number,
            "operation_id": operation_id,
            "table_name": table_name,
            "date_raw": r.get("date"),
            "time_raw": r.get("time"),
            "recorded_by": r.get("recorded_by"),
            "value_raw": r.get("value"),
            "page_no": page_no,
        }
        for r in rows
    ]
    if db_rows:
        client.table("timeseries_readings").insert(db_rows).execute()


def load_rich_operations(batch_number: str) -> list:
    """Returns operations + their materials, in the shape chronology_checker
    and material_reconciler expect."""
    client = get_client()
    op_result = client.table("operations").select("*").eq("batch_number", batch_number).execute()
    mat_result = client.table("operation_materials").select("*").eq("batch_number", batch_number).execute()

    materials_by_op = {}
    for row in mat_result.data:
        materials_by_op.setdefault(row["operation_id"], []).append(
            {"material": row["material"], "qty_used": row["qty_used_raw"]}
        )

    return [
        {
            "operation_id": row["operation_id"],
            "description": row.get("description"),
            "page_no": row.get("page_no"),
            "operator": row.get("operator"),
            "start_time": row.get("start_time_raw"),
            "end_time": row.get("end_time_raw"),
            "materials": materials_by_op.get(row["operation_id"], []),
        }
        for row in op_result.data
    ]


def load_timeseries_readings(batch_number: str, table_name: str = None) -> list:
    client = get_client()
    query = client.table("timeseries_readings").select("*").eq("batch_number", batch_number)
    if table_name:
        query = query.eq("table_name", table_name)
    result = query.execute()
    return [
        {
            "date": r.get("date_raw"),
            "time": r.get("time_raw"),
            "recorded_by": r.get("recorded_by"),
            "value": r.get("value_raw"),
        }
        for r in result.data
    ]
