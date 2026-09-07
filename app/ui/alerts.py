import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from app.services.analytics.inventory_analytics import compute_system_alerts

def render_alerts_page(db: Session):
    st.title("System Alerts & Operational Exceptions")
    st.caption("Active supply chain alerts, stock discrepancies, and specification conflict warnings")

    from app.database.models import Material
    if db.query(Material).count() == 0:
        st.info("No materials loaded yet — please upload a file or load the demo dataset to view system alerts.")
        return

    alerts = compute_system_alerts(db)

    # Filter controls
    col_s, col_t = st.columns(2)
    with col_s:
        sev_filter = st.selectbox("Filter Severity", ["All Severities", "Critical", "Warning", "Info"])
    with col_t:
        all_types = ["All Types"] + sorted(list(set(a["type"] for a in alerts)))
        type_filter = st.selectbox("Filter Alert Type", all_types)

    filtered = alerts
    if sev_filter != "All Severities":
        filtered = [a for a in filtered if a["severity"] == sev_filter]
    if type_filter != "All Types":
        filtered = [a for a in filtered if a["type"] == type_filter]

    st.markdown(f"**Showing {len(filtered)} active alerts**")

    if not filtered:
        st.success("No alerts found matching the selected filters.")
        return

    for alert in filtered:
        sev = alert["severity"]
        if sev == "Critical":
            border_col = "#ea4335"
            bg_col = "#fce8e6"
        elif sev == "Warning":
            border_col = "#f2994a"
            bg_col = "#fef7e0"
        else:
            border_col = "#1a73e8"
            bg_col = "#e8f0fe"

        st.markdown(
            f'<div style="border-left: 5px solid {border_col}; background: {bg_col}; padding: 12px 16px; border-radius: 6px; margin-bottom: 12px;">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">'
            f'<span style="font-weight: 700; font-size: 15px; color: #202124;">[{sev.upper()}] {alert["title"]}</span>'
            f'<span style="font-size: 12px; font-weight: 600; color: #5f6368;">Entity: {alert["entity"]}</span>'
            f'</div>'
            f'<div style="font-size: 13px; color: #3c4043;">{alert["description"]}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
