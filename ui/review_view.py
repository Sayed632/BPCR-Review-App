"""
ui/review_view.py
Displays the observation report and lets the reviewer export it.
"""

import streamlit as st
from core.report_builder import export_to_excel, summarize


def show_report(df):
    st.subheader("Observation Report")

    summary = summarize(df)
    cols = st.columns(5)
    cols[0].metric("Total Fields", summary["total_fields"])
    cols[1].metric("In Range", summary["in_range"])
    cols[2].metric("Out of Range", summary["out_of_range"])
    cols[3].metric("Missing", summary["missing"])
    cols[4].metric("Illegible", summary["illegible"])

    def highlight_status(row):
        if row["status"] == "OUT_OF_RANGE":
            return ["background-color: #ffcccc"] * len(row)
        elif row["status"] in ("MISSING_ENTRY", "ILLEGIBLE", "EXTRACTION_FAILED"):
            return ["background-color: #fff3cd"] * len(row)
        elif row["status"] == "IN_RANGE":
            return ["background-color: #d4edda"] * len(row)
        return [""] * len(row)

    st.dataframe(df.style.apply(highlight_status, axis=1), use_container_width=True)

    if st.button("Export to Excel"):
        filepath = export_to_excel(df)
        with open(filepath, "rb") as f:
            st.download_button(
                "Download Report",
                data=f.read(),
                file_name=filepath.split("/")[-1],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
