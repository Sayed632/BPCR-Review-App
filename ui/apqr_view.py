"""
ui/apqr_view.py
Displays cross-batch trend tables for APQR / data analysis, with a
one-click Excel export of everything as a multi-sheet workbook.
"""

import streamlit as st
from core.apqr_export import (
    build_batch_list,
    build_parameter_pivot_table,
    build_parameter_trend_table,
    build_deviation_rate_table,
    build_material_usage_trend,
    export_apqr_workbook,
)


def show_apqr_dashboard(product_name: str):
    st.header("APQR / Cross-Batch Data Analysis")
    st.caption(f"Aggregated across every saved batch of **{product_name}**.")

    batches_df = build_batch_list(product_name)
    if batches_df.empty:
        st.info("No batches saved yet for this product. Process at least one batch first.")
        return

    st.metric("Batches on record", len(batches_df))

    with st.expander("Batches"):
        st.dataframe(batches_df, use_container_width=True)

    st.subheader("Parameter Summary (one row per batch)")
    pivot_df = build_parameter_pivot_table(product_name)
    st.dataframe(pivot_df, use_container_width=True)

    st.subheader("Deviation Rate by Batch")
    deviation_df = build_deviation_rate_table(product_name)
    if not deviation_df.empty:
        st.bar_chart(deviation_df.set_index("batch_number")[["in_range", "out_of_range", "missing", "illegible"]])
    st.dataframe(deviation_df, use_container_width=True)

    st.subheader("Material Usage Trend")
    material_trend_df = build_material_usage_trend(product_name)
    st.dataframe(material_trend_df, use_container_width=True)

    with st.expander("Full parameter observation detail"):
        st.dataframe(build_parameter_trend_table(product_name), use_container_width=True)

    st.divider()
    if st.button("Export Full APQR Workbook (Excel)"):
        import os
        os.makedirs("outputs", exist_ok=True)
        path = f"outputs/apqr_{product_name.replace(' ', '_')}.xlsx"
        export_apqr_workbook(product_name, path)
        with open(path, "rb") as f:
            st.download_button(
                "Download APQR Workbook",
                data=f.read(),
                file_name=path.split("/")[-1],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
