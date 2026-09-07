import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import Session
from app.database.models import Material, HarmonizedMaterial, MatchResult, Inventory
from app.services.analytics.financial_analytics import compute_financial_analytics
from app.services.analytics.inventory_analytics import compute_system_alerts, get_harmonized_inventory_aggregation
from app.services.ingestion.demo_loader import load_demo_dataset
from app.services.matching.candidate_search import run_candidate_search_and_matching
from app.utils.formatting import format_inr, get_status_badge

def render_overview_page(db: Session):
    st.title("Executive Dashboard — NMC Harmonizer")
    st.caption("National Material Code Harmonization across Central Public Sector Enterprises (IOCL, BPCL, HPCL, ONGC, GAIL)")

    # Action Bar: Demo Dataset Loader & Run Harmonization
    col_btn1, col_btn2, col_info = st.columns([1.5, 2, 4])
    with col_btn1:
        if st.button("📥 Load Demo Dataset", help="Re-initializes demo materials across CPSEs"):
            with st.spinner("Loading synthetic CPSE dataset..."):
                ok, msg = load_demo_dataset(db)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with col_btn2:
        if st.button("🚀 Run AI Harmonization", type="primary", help="Runs normalization, embeddings, FAISS retrieval, and scoring"):
            progress_bar = st.progress(0, text="Initializing harmonization pipeline...")
            def update_progress(text, val):
                progress_bar.progress(val, text=text)

            matches = run_candidate_search_and_matching(db, progress_callback=update_progress)
            st.success(f"Harmonization complete! Identified {len(matches)} candidate matches.")
            st.rerun()

    with col_info:
        st.markdown(
            '<div style="background:#e8f0fe; padding:10px 14px; border-radius:8px; font-size:13px; color:#1e40af; border:1px solid #bfdbfe; border-left:4px solid #1a73e8;">'
            '<b style="color:#1e3a8a;">Harmonization Pipeline:</b> Normalization &rarr; Attribute Extraction &rarr; MiniLM Vector Index &rarr; FAISS Top-K Candidate Search &rarr; Spec-Aware Scoring &rarr; Explainable Review'
            '</div>',
            unsafe_allow_html=True
        )

    st.markdown("---")

    # Metrics calculation
    total_materials = db.query(Material).count()
    if total_materials == 0:
        st.info(
            "💡 **Pristine Environment — No materials loaded yet.**\n\n"
            "The database is currently clean and empty. To get started, you can:\n"
            "- Click **📥 Load Demo Dataset** above to populate the benchmark multi-CPSE dataset (IOCL, BPCL, HPCL, GAIL, ONGC), or\n"
            "- Navigate to **Materials &rarr; 📥 Data Ingestion & Import** to upload your own CPSE inventory spreadsheet (.xlsx or .csv).\n\n"
            "Once data is loaded, click **🚀 Run AI Harmonization** to automatically detect cross-CPSE duplicates, group matching materials, and generate Common Material Codes."
        )
        return

    harmonized_count = db.query(HarmonizedMaterial).count()

    from app.database.models import MatchGroup
    auto_approved_groups = db.query(MatchGroup).filter(MatchGroup.reviewed_by == "AI Auto-Approval").count()
    pending_groups = db.query(MatchGroup).filter(MatchGroup.status == "pending").count()
    pending_pairs = db.query(MatchResult).filter(MatchResult.status == "pending").count()
    pending_human_review = pending_groups if (pending_groups > 0 or auto_approved_groups > 0) else pending_pairs

    fin = compute_financial_analytics(db)
    alerts = compute_system_alerts(db)

    low_stock_count = sum(1 for a in alerts if a["type"] == "LOW STOCK")
    out_stock_count = sum(1 for a in alerts if a["type"] == "OUT OF STOCK")
    duplicate_items_count = sum(1 for a in alerts if a["type"] == "DUPLICATE INVENTORY")

    # KPI Cards row 1: Split into Auto-Approved by AI and Pending Human Review
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    with kpi_col1:
        st.metric(label="Total Materials", value=f"{total_materials:,}")
    with kpi_col2:
        st.metric(label="Harmonized Codes (CMC)", value=f"{harmonized_count:,}")
    with kpi_col3:
        st.metric(label="Duplicate Groups", value=f"{duplicate_items_count:,}", delta="Cross-CPSE Duplication", delta_color="inverse")
    with kpi_col4:
        st.metric(label="Auto-Approved by AI", value=f"{auto_approved_groups:,}", delta="Zero Human Effort", delta_color="normal")
    with kpi_col5:
        st.metric(
            label="Pending Human Review",
            value=f"{pending_human_review:,}",
            delta="Action Needed" if pending_human_review > 0 else "All Cleared",
            delta_color="inverse" if pending_human_review > 0 else "normal"
        )

    # KPI Cards row 2
    kpi_col5, kpi_col6, kpi_col7, kpi_col8 = st.columns(4)
    with kpi_col5:
        st.metric(label="Total Inventory Value", value=format_inr(fin["total_inventory_value"]))
    with kpi_col6:
        st.metric(label="Potential Working Capital Release", value=format_inr(fin["potential_working_capital_release"]), help="Prototype Estimate based on 35% duplicate stock release")
    with kpi_col7:
        st.metric(label="Low Stock Alerts", value=f"{low_stock_count}", delta_color="inverse")
    with kpi_col8:
        st.metric(label="Out-of-Stock Items", value=f"{out_stock_count}", delta_color="inverse")

    st.caption("⚠️ *All financial metrics are labeled **Prototype Estimate** for Smart India Hackathon presentation.*")

    # Row of Charts
    st.markdown("### 📊 Enterprise Analytics & Material Distribution")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # Inventory Value by Category
        if fin["value_by_category"]:
            cat_df = pd.DataFrame(list(fin["value_by_category"].items()), columns=["Category", "Value (INR)"])
            fig_cat = px.bar(
                cat_df, x="Category", y="Value (INR)",
                title="Inventory Value by Category",
                color="Value (INR)",
                color_continuous_scale="Blues"
            )
            fig_cat.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No category inventory data available.")

    with chart_col2:
        # Material Harmonization Status Pie Chart
        raw_count = db.query(Material).filter(Material.status == "raw").count()
        proc_count = db.query(Material).filter(Material.status == "processed").count()
        mapped_count = db.query(Material).filter(Material.status == "mapped").count()
        
        status_df = pd.DataFrame({
            "Status": ["Harmonized & Mapped", "Processed (Ready)", "Raw Ingested"],
            "Count": [mapped_count, proc_count, raw_count]
        })
        fig_status = px.pie(
            status_df, names="Status", values="Count",
            title="Material Harmonization Status",
            color="Status",
            color_discrete_map={
                "Harmonized & Mapped": "#137333",
                "Processed (Ready)": "#1a73e8",
                "Raw Ingested": "#f9ab00"
            },
            hole=0.45
        )
        fig_status.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_status, use_container_width=True)

    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        # Duplicate Materials count by CPSE
        if fin["duplicate_count_by_cpse"]:
            cpse_dupe_df = pd.DataFrame(
                list(fin["duplicate_count_by_cpse"].items()),
                columns=["CPSE", "Duplicate Material Instances"]
            )
            fig_dupe = px.bar(
                cpse_dupe_df, x="CPSE", y="Duplicate Material Instances",
                title="Cross-CPSE Duplicate Stock Holdings",
                color="CPSE",
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_dupe.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_dupe, use_container_width=True)
        else:
            st.info("Run AI Harmonization to discover cross-CPSE duplicate materials.")

    with chart_col4:
        # Potential Savings by Category
        if fin["avoidable_by_category"]:
            sav_df = pd.DataFrame(
                list(fin["avoidable_by_category"].items()),
                columns=["Category", "Estimated Avoidable Procurement (INR)"]
            )
            fig_sav = px.pie(
                sav_df, names="Category", values="Estimated Avoidable Procurement (INR)",
                title="Estimated Avoidable Procurement by Category (Prototype Estimate)",
                color_discrete_sequence=px.colors.sequential.Teal
            )
            fig_sav.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_sav, use_container_width=True)
        else:
            st.info("Potential savings will appear after harmonizing duplicate materials.")

    # Tables: Critical Alerts & Top Materials
    st.markdown("### 🔔 Active Priority Alerts")
    critical_alerts = [a for a in alerts if a["severity"] in ["Critical", "Warning"]][:5]
    if critical_alerts:
        for a in critical_alerts:
            color = "#ea4335" if a["severity"] == "Critical" else "#f2994a"
            bg_color = "#fef2f2" if a["severity"] == "Critical" else "#fffbeb"
            border_color = "#fecaca" if a["severity"] == "Critical" else "#fde68a"
            text_title_color = "#991b1b" if a["severity"] == "Critical" else "#92400e"
            st.markdown(
                f'<div style="border-left: 4px solid {color}; border-top: 1px solid {border_color}; border-right: 1px solid {border_color}; border-bottom: 1px solid {border_color}; padding: 10px 14px; margin-bottom: 8px; background: {bg_color}; border-radius: 6px; color: #1f2937;">'
                f'<b style="color: {text_title_color};">[{a["severity"]}] {a["title"]}</b> &mdash; <span style="color: #374151;">{a["description"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.success("No critical inventory or specification alerts at this moment.")
