import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from app.services.analytics.financial_analytics import compute_financial_analytics
from app.services.analytics.inventory_analytics import get_harmonized_inventory_aggregation
from app.utils.formatting import format_inr

def render_procurement_page(db: Session):
    st.title("Procurement Optimization & Avoidable Spend Insights")
    st.caption("AI-driven duplicate stock detection to reduce redundant tendering and bulk purchase duplication")

    from app.database.models import Material
    if db.query(Material).count() == 0:
        st.info("No materials loaded yet — please upload a file or load the demo dataset to view procurement insights.")
        return

    fin = compute_financial_analytics(db)
    agg = get_harmonized_inventory_aggregation(db)

    # Top KPI banners
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="Duplicate Inventory Value",
            value=format_inr(fin["duplicate_inventory_value"]),
            help="Value of overlapping inventory across CPSEs"
        )
    with col2:
        st.metric(
            label="Estimated Avoidable Procurement",
            value=format_inr(fin["avoidable_procurement_value"]),
            help="Prototype Estimate based on 25% avoided redundant purchase orders"
        )
    with col3:
        st.metric(
            label="Annual Holding Cost Savings",
            value=format_inr(fin["annual_holding_cost_savings"]),
            help="Prototype Estimate based on 18% carrying cost reduction"
        )

    st.caption("⚠️ *Figures labeled **Prototype Estimate** — derived from configurable parameters in `weights.yaml`.*")

    st.markdown("### 📋 Inter-CPSE Transfer & Avoidable Procurement Recommendations")
    recommendations = []
    for item in agg:
        if item["is_duplicate_stock"]:
            cpses = list(item["cpse_breakdown"].keys())
            recommendations.append({
                "Common Material Code": item["common_code"],
                "Description": item["standard_description"],
                "Category": item["category"],
                "Total Available Across CPSEs": f"{item['total_available']:,.0f} {item['uom']}",
                "CPSE Entities": ", ".join(cpses),
                "Potential Avoided Spend": format_inr(item["total_value"] * 0.25),
                "Recommended Procurement Action": f"Hold new tenders; consolidate purchase or arrange stock transfer among {', '.join(cpses)}"
            })

    if recommendations:
        st.dataframe(pd.DataFrame(recommendations), use_container_width=True, hide_index=True)
    else:
        st.info("No cross-CPSE duplicate procurement recommendations active at this moment.")
