"""
ui/alcoa_view.py
Displays chronology (attributability) conflicts and material
reconciliation results.
"""

import streamlit as st
import pandas as pd


def show_chronology(chronology_result: dict):
    st.subheader("Chronology / Attributability Check")

    conflicts = chronology_result.get("conflicts", [])
    unparseable = chronology_result.get("unparseable", [])

    if not conflicts:
        st.success("No overlapping-timestamp conflicts detected.")
    else:
        st.error(f"{len(conflicts)} chronology conflict(s) detected — same operator, same time, different operations.")
        st.dataframe(pd.DataFrame(conflicts), use_container_width=True)

    if unparseable:
        st.warning(f"{len(unparseable)} entries had unreadable/unparseable timestamps.")
        st.dataframe(pd.DataFrame(unparseable), use_container_width=True)


def show_reconciliation(reconciliation_result: dict):
    st.subheader("Material Quantity Reconciliation")

    details = reconciliation_result.get("details", [])
    summary = reconciliation_result.get("summary", [])

    if summary:
        summary_df = pd.DataFrame(summary)

        def highlight(row):
            if row["status"] == "OVER_CONSUMED":
                return ["background-color: #ffcccc"] * len(row)
            elif row["status"] == "EXCESS_LOSS":
                return ["background-color: #fff3cd"] * len(row)
            elif row["status"] == "RECONCILED":
                return ["background-color: #d4edda"] * len(row)
            return [""] * len(row)

        st.dataframe(summary_df.style.apply(highlight, axis=1), use_container_width=True)

    if details:
        with st.expander("Per-operation consumption detail"):
            st.dataframe(pd.DataFrame(details), use_container_width=True)
