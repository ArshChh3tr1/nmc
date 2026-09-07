import streamlit as st
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.db import init_db, SessionLocal
from app.ui.auth import render_role_selector, get_current_user_role, get_current_username
from app.ui.overview import render_overview_page
from app.ui.materials import render_materials_page
from app.ui.harmonization import render_harmonization_page
from app.ui.inventory import render_inventory_page
from app.ui.warehouses import render_warehouses_page
from app.ui.procurement import render_procurement_page
from app.ui.suppliers import render_suppliers_page
from app.ui.reports import render_reports_page
from app.ui.alerts import render_alerts_page
from app.ui.audit_trail import render_audit_trail_page
from app.ui.settings import render_settings_page

# Configure page metadata
st.set_page_config(
    page_title="NMC Harmonizer | National Material Code Harmonization",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom enterprise styling (light/clean industrial portal)
st.markdown("""
<style>
    /* Clean layout styling */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* Top banner - resilient responsive layout */
    .top-gov-bar {
        background: linear-gradient(90deg, #1a365d 0%, #2b6cb0 100%) !important;
        color: #ffffff !important;
        padding: 10px 18px !important;
        border-radius: 8px !important;
        margin-bottom: 1.25rem !important;
        min-height: 48px !important;
        display: flex !important;
        flex-direction: row !important;
        justify-content: space-between !important;
        align-items: center !important;
        flex-wrap: wrap !important;
        gap: 10px 16px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        line-height: 1.5 !important;
        overflow: visible !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08) !important;
    }

    .top-gov-bar * {
        color: #ffffff !important;
    }

    /* Metric cards styling: explicit background and explicit text colors */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        padding: 14px 18px !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    
    div[data-testid="stMetric"]:hover {
        border-color: #3182ce !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricLabel"],
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] *,
    div[data-testid="stMetric"] label {
        color: #4b5563 !important;
        font-weight: 600 !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"],
    div[data-testid="stMetric"] [data-testid="stMetricValue"] * {
        color: #111827 !important;
        font-weight: 700 !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricDelta"],
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] * {
        font-weight: 600 !important;
    }

    /* Card styling */
    .stCard {
        background: #ffffff !important;
        color: #111827 !important;
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        padding: 16px !important;
    }
    .stCard * {
        color: inherit;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Initialize DB tables
    init_db()
    db = SessionLocal()

    # Top Gov/Enterprise Header - Robust flex wrapping container
    st.markdown("""
    <div class="top-gov-bar">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span>🇮🇳</span>
            <span style="font-weight: 600; font-size: 13px; letter-spacing: 0.2px;">Government of India &bull; Ministry of Petroleum & Natural Gas &bull; Smart India Hackathon</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <span style="background: rgba(255, 255, 255, 0.18); border: 1px solid rgba(255, 255, 255, 0.35); padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; white-space: nowrap;">
                <b>NMC Harmonizer</b> v1.0.0 (Offline Native Prototype)
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Left Sidebar Navigation
    st.sidebar.markdown("### 🏛️ NMC Harmonizer")
    st.sidebar.caption("National Material Code Harmonization Platform")

    # Role Selector (Persona Switcher)
    render_role_selector()

    st.sidebar.markdown("---")
    st.sidebar.markdown("##### Navigation")

    nav_pages = [
        "Overview",
        "Materials",
        "AI Harmonization",
        "Inventory",
        "Warehouses",
        "Procurement",
        "Suppliers",
        "Reports",
        "Alerts",
        "Audit Trail",
        "Settings"
    ]

    selected_page = st.sidebar.radio(
        "Go to Page",
        nav_pages,
        index=0,
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f'<div style="font-size:12px; color:#374151; background:#f3f4f6; border:1px solid #e5e7eb; border-radius:6px; padding:8px 10px; margin-top:8px;">'
        f'Active User: <b style="color:#111827;">{get_current_username()}</b><br>'
        f'Role: <b style="color:#111827;">{get_current_user_role()}</b><br>'
        f'Model: <code style="color:#1e3a8a; background:#e5e7eb;">all-MiniLM-L6-v2 (CPU)</code>'
        f'</div>',
        unsafe_allow_html=True
    )

    try:
        if selected_page == "Overview":
            render_overview_page(db)
        elif selected_page == "Materials":
            render_materials_page(db)
        elif selected_page == "AI Harmonization":
            render_harmonization_page(db)
        elif selected_page == "Inventory":
            render_inventory_page(db)
        elif selected_page == "Warehouses":
            render_warehouses_page(db)
        elif selected_page == "Procurement":
            render_procurement_page(db)
        elif selected_page == "Suppliers":
            render_suppliers_page(db)
        elif selected_page == "Reports":
            render_reports_page(db)
        elif selected_page == "Alerts":
            render_alerts_page(db)
        elif selected_page == "Audit Trail":
            render_audit_trail_page(db)
        elif selected_page == "Settings":
            render_settings_page(db)
    finally:
        db.close()

if __name__ == "__main__":
    main()
