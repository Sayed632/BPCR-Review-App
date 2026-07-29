"""
core/report_builder.py
Compiles evaluated field rows into an observation report,
viewable in-app and exportable to Excel.
"""

import pandas as pd
from datetime import datetime
import os


REPORT_COLUMNS = [
    "page_no",
    "parameter",
    "spec_instruction",
    "written_value",
    "status",
    "deviation_type",
    "model_used",
]


def build_report_df(evaluated_rows: list) -> pd.DataFrame:
    df = pd.DataFrame(evaluated_rows, columns=REPORT_COLUMNS)
    df = df.sort_values(by=["page_no"]).reset_index(drop=True)
    return df


def export_to_excel(df: pd.DataFrame, outputs_dir: str = "outputs") -> str:
    os.makedirs(outputs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(outputs_dir, f"observation_report_{timestamp}.xlsx")
    df.to_excel(filepath, index=False)
    return filepath


def summarize(df: pd.DataFrame) -> dict:
    return {
        "total_fields": len(df),
        "in_range": (df["status"] == "IN_RANGE").sum(),
        "out_of_range": (df["status"] == "OUT_OF_RANGE").sum(),
        "missing": (df["status"] == "MISSING_ENTRY").sum(),
        "illegible": (df["status"] == "ILLEGIBLE").sum(),
        "extraction_failed": (df["status"] == "EXTRACTION_FAILED").sum(),
    }
