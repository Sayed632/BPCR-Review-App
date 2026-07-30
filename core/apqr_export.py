"""
core/apqr_export.py
Aggregates persisted data across all batches of a product into
analysis-ready tables - the core input for an Annual Product Quality
Review (APQR) or any other batch-to-batch trend analysis.
"""

import pandas as pd
from core.storage import (
    load_all_batches,
    load_all_parameter_observations,
    load_all_operation_materials,
)
from core.material_reconciler import _parse_qty


def build_parameter_trend_table(product_name: str) -> pd.DataFrame:
    """
    One row per (batch, parameter) observation across every batch of
    this product - the raw form needed for control charts / trending
    a single parameter (e.g. Reflux Temperature) over time.
    """
    rows = load_all_parameter_observations(product_name)
    if not rows:
        return pd.DataFrame(
            columns=["batch_number", "parameter", "written_value", "status", "spec_instruction", "created_at"]
        )
    df = pd.DataFrame(rows)
    keep_cols = [c for c in ["batch_number", "parameter", "written_value", "status",
                              "spec_instruction", "deviation_type", "created_at"] if c in df.columns]
    return df[keep_cols].sort_values(["parameter", "batch_number"])


def build_parameter_pivot_table(product_name: str) -> pd.DataFrame:
    """
    Wide/pivoted view: one row per batch, one column per parameter -
    the classic APQR-style summary table for a quick cross-batch scan.
    """
    df = build_parameter_trend_table(product_name)
    if df.empty:
        return df
    pivot = df.pivot_table(
        index="batch_number", columns="parameter", values="written_value", aggfunc="first"
    )
    return pivot.reset_index()


def build_deviation_rate_table(product_name: str) -> pd.DataFrame:
    """
    Per-batch deviation counts by status - shows whether a product's
    deviation rate is trending up/down/stable across batches, a
    standard APQR question.
    """
    df = build_parameter_trend_table(product_name)
    if df.empty:
        return pd.DataFrame(columns=["batch_number", "in_range", "out_of_range", "missing", "illegible", "total"])

    summary = (
        df.groupby(["batch_number", "status"]).size().unstack(fill_value=0).reset_index()
    )
    for col in ["IN_RANGE", "OUT_OF_RANGE", "MISSING_ENTRY", "ILLEGIBLE"]:
        if col not in summary.columns:
            summary[col] = 0

    summary["total"] = summary[[c for c in summary.columns if c != "batch_number"]].sum(axis=1)
    summary = summary.rename(
        columns={
            "IN_RANGE": "in_range",
            "OUT_OF_RANGE": "out_of_range",
            "MISSING_ENTRY": "missing",
            "ILLEGIBLE": "illegible",
        }
    )
    cols = ["batch_number", "in_range", "out_of_range", "missing", "illegible", "total"]
    return summary[[c for c in cols if c in summary.columns]]


def build_material_usage_trend(product_name: str) -> pd.DataFrame:
    """
    Per-batch, per-material total quantity used - lets you spot a
    material whose consumption is drifting across batches, another
    standard APQR trending question.
    """
    rows = load_all_operation_materials(product_name)
    if not rows:
        return pd.DataFrame(columns=["batch_number", "material", "qty_used_total"])

    df = pd.DataFrame(rows)
    df["qty_parsed"] = df["qty_used_raw"].apply(_parse_qty)
    grouped = (
        df.groupby(["batch_number", "material"])["qty_parsed"]
        .sum()
        .reset_index()
        .rename(columns={"qty_parsed": "qty_used_total"})
    )
    return grouped.sort_values(["material", "batch_number"])


def build_batch_list(product_name: str) -> pd.DataFrame:
    batches = load_all_batches(product_name)
    if not batches:
        return pd.DataFrame(columns=["batch_number", "product_name", "spec_version", "created_at"])
    return pd.DataFrame(batches)[["batch_number", "product_name", "spec_version", "created_at"]]


def export_apqr_workbook(product_name: str, output_path: str) -> str:
    """
    Builds a multi-sheet Excel workbook ready to hand to an APQR
    author or feed into further statistical analysis.
    """
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        build_batch_list(product_name).to_excel(writer, sheet_name="Batches", index=False)
        build_parameter_pivot_table(product_name).to_excel(writer, sheet_name="Parameter Summary", index=False)
        build_parameter_trend_table(product_name).to_excel(writer, sheet_name="Parameter Detail", index=False)
        build_deviation_rate_table(product_name).to_excel(writer, sheet_name="Deviation Rates", index=False)
        build_material_usage_trend(product_name).to_excel(writer, sheet_name="Material Usage Trend", index=False)
    return output_path
