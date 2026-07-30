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


def show_personnel_check(validation_results: list):
    st.subheader("Personnel / Attributability Check")

    unrecognized = [r for r in validation_results if r["status"] == "UNRECOGNIZED"]
    fuzzy = [r for r in validation_results if r["status"] == "FUZZY_MATCHED"]

    if unrecognized:
        st.error(f"{len(unrecognized)} entries signed by a name not on the Signature Table.")
        st.dataframe(pd.DataFrame(unrecognized), use_container_width=True)
    else:
        st.success("All recognized operator entries matched the Signature Table.")

    if fuzzy:
        st.warning(f"{len(fuzzy)} entries matched only approximately (handwriting variance) — worth a visual check.")
        st.dataframe(pd.DataFrame(fuzzy), use_container_width=True)


def show_timeseries_issues(operation_id: str, table_name: str, result: dict):
    out_of_range = result.get("out_of_range", [])
    missed = result.get("missed_intervals", [])
    unparseable = result.get("unparseable_rows", [])

    if not out_of_range and not missed and not unparseable:
        st.success(f"{table_name} ({operation_id}): all readings in range, no missed intervals.")
        return

    st.warning(f"{table_name} ({operation_id}): issues found.")
    if out_of_range:
        st.write("Out-of-range readings:")
        st.dataframe(pd.DataFrame(out_of_range), use_container_width=True)
    if missed:
        st.write("Missed/late intervals:")
        st.dataframe(pd.DataFrame(missed), use_container_width=True)
    if unparseable:
        st.write("Unparseable rows:")
        st.dataframe(pd.DataFrame(unparseable), use_container_width=True)
