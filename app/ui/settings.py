import streamlit as st
import yaml
from sqlalchemy.orm import Session
from app.config import get_weights_config, update_weights_config, get_taxonomy_config, update_taxonomy_config
from app.ui.auth import get_current_user_role
from app.services.classification.classifier import get_classifier

def render_settings_page(db: Session):
    st.title("System Configuration & Scoring Parameters")
    st.caption("Manage AI matching weights, classification bands, and taxonomy tree")

    user_role = get_current_user_role()
    if user_role != "Admin":
        st.warning("⚠️ **Access Restricted:** Configuration settings can only be modified by users with the **Admin** role. Please switch your persona to 'Admin' in the sidebar dropdown to enable editing.")
        st.info("Displaying current settings in read-only mode.")

    tab_weights, tab_tax, tab_fin, tab_db = st.tabs([
        "⚖️ Matching Weights & Thresholds",
        "📂 Taxonomy Tree Editor",
        "💡 Financial Assumptions",
        "🗑️ Database Administration"
    ])

    cfg = get_weights_config()
    weights = cfg["weights"]
    thresholds = cfg["thresholds"]
    financial = cfg["financial_assumptions"]

    with tab_weights:
        st.subheader("Weighted Scoring Pipeline Components")
        st.write("Configured in `config/weights.yaml`. Must sum to 1.0.")

        col1, col2 = st.columns(2)
        with col1:
            w_sem = st.slider("Semantic Similarity Weight", 0.0, 1.0, float(weights.get("semantic_similarity", 0.40)), 0.05, disabled=(user_role != "Admin"))
            w_mat = st.slider("Material Match Weight", 0.0, 1.0, float(weights.get("material_match", 0.20)), 0.05, disabled=(user_role != "Admin"))
            w_dim = st.slider("Dimension Match Weight", 0.0, 1.0, float(weights.get("dimension_match", 0.15)), 0.05, disabled=(user_role != "Admin"))

        with col2:
            w_cat = st.slider("Category Match Weight", 0.0, 1.0, float(weights.get("category_match", 0.10)), 0.05, disabled=(user_role != "Admin"))
            w_spec = st.slider("Specification Match Weight", 0.0, 1.0, float(weights.get("specification_match", 0.10)), 0.05, disabled=(user_role != "Admin"))
            w_uom = st.slider("UOM Match Weight", 0.0, 1.0, float(weights.get("uom_match", 0.05)), 0.05, disabled=(user_role != "Admin"))

        total_w = round(w_sem + w_mat + w_dim + w_cat + w_spec + w_uom, 2)
        st.write(f"**Total Weight Sum:** `{total_w}` {'✅ (Valid)' if total_w == 1.0 else '⚠️ (Should sum to 1.0)'}")

        st.subheader("Confidence Score Thresholds")
        c_th1, c_th2 = st.columns(2)
        with c_th1:
            th_exact = st.number_input("Exact Duplicate Min Confidence (%)", 80.0, 100.0, float(thresholds.get("exact_duplicate_min", 95.0)), 1.0, disabled=(user_role != "Admin"))
            th_high = st.number_input("High Confidence Min (%)", 70.0, 95.0, float(thresholds.get("high_confidence_min", 90.0)), 1.0, disabled=(user_role != "Admin"))
        with c_th2:
            th_med = st.number_input("Medium Confidence Min (%)", 50.0, 90.0, float(thresholds.get("medium_confidence_min", 80.0)), 1.0, disabled=(user_role != "Admin"))
            th_low = st.number_input("Low Confidence Min (%)", 30.0, 70.0, float(thresholds.get("low_confidence_min", 60.0)), 1.0, disabled=(user_role != "Admin"))

        st.subheader("🤖 AI Auto-Approval Rules Engine")
        st.write(
            "When enabled, candidate material groups whose **Min Confidence** meets or exceeds this threshold "
            "and are classified as **Exact Duplicate** or **Near Duplicate** are automatically approved without manual intervention."
        )
        c_auto1, c_auto2 = st.columns(2)
        with c_auto1:
            auto_enabled = st.toggle(
                "Enable AI Auto-Approval",
                value=bool(cfg.get("auto_approve", {}).get("enabled", True)),
                disabled=(user_role != "Admin"),
                help="Automatically approves high-confidence duplicate groups during the AI harmonization run"
            )
        with c_auto2:
            auto_thresh = st.slider(
                "Auto-Approval Minimum Confidence Threshold (%)",
                85.0, 99.0,
                float(cfg.get("auto_approve", {}).get("threshold", 95.0)),
                0.5,
                disabled=(user_role != "Admin"),
                help="Groups with minimum link confidence at or above this score qualify for automated approval"
            )

        if user_role == "Admin":
            if st.button("Save Configuration", type="primary"):
                new_weights = {
                    "semantic_similarity": w_sem,
                    "material_match": w_mat,
                    "dimension_match": w_dim,
                    "category_match": w_cat,
                    "specification_match": w_spec,
                    "uom_match": w_uom
                }
                new_thresholds = {
                    "exact_duplicate_min": th_exact,
                    "high_confidence_min": th_high,
                    "medium_confidence_min": th_med,
                    "low_confidence_min": th_low
                }
                new_auto = {
                    "enabled": auto_enabled,
                    "threshold": auto_thresh
                }
                update_weights_config(weights=new_weights, thresholds=new_thresholds, auto_approve=new_auto)
                st.success("Successfully updated `config/weights.yaml`!")

    with tab_tax:
        st.subheader("Category Taxonomy Configuration (`config/taxonomy.yaml`)")
        tax = get_taxonomy_config()
        raw_tax_yaml = yaml.safe_dump(tax, sort_keys=False)

        tax_text = st.text_area(
            "Taxonomy YAML Definition",
            value=raw_tax_yaml,
            height=350,
            disabled=(user_role != "Admin")
        )

        if user_role == "Admin":
            if st.button("Save Taxonomy Changes"):
                try:
                    parsed_tax = yaml.safe_load(tax_text)
                    update_taxonomy_config(parsed_tax)
                    get_classifier().reload_taxonomy()
                    st.success("Taxonomy updated successfully and classifier reloaded!")
                except Exception as e:
                    st.error(f"Invalid YAML format: {str(e)}")

    with tab_fin:
        st.subheader("Prototype Financial Estimate Assumptions")
        st.caption("Configurable parameters for estimated working capital and procurement savings calculations")

        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            wc_pct = st.number_input(
                "Working Capital Release %",
                0.05, 0.95, float(financial.get("working_capital_release_pct", 0.35)), 0.05,
                disabled=(user_role != "Admin")
            )
        with f_col2:
            proc_pct = st.number_input(
                "Avoidable Procurement %",
                0.05, 0.95, float(financial.get("avoidable_procurement_pct", 0.25)), 0.05,
                disabled=(user_role != "Admin")
            )
        with f_col3:
            hold_pct = st.number_input(
                "Annual Holding Cost %",
                0.05, 0.50, float(financial.get("holding_cost_annual_pct", 0.18)), 0.01,
                disabled=(user_role != "Admin")
            )

        if user_role == "Admin":
            if st.button("Save Financial Assumptions"):
                new_fin = {
                    "working_capital_release_pct": wc_pct,
                    "avoidable_procurement_pct": proc_pct,
                    "holding_cost_annual_pct": hold_pct
                }
                update_weights_config(financial=new_fin)
                st.success("Financial assumptions updated in `config/weights.yaml`!")

    with tab_db:
        st.subheader("Database Management & Reset")
        st.markdown(
            "> [!WARNING]\n"
            "> **Clear All Data:** Safely wipes all ingested material master records, warehouse inventory, "
            "> AI match results, match groups, mappings, and audit history. Reverts the application to a pristine empty state "
            "> ready for fresh demonstration or custom file upload."
        )

        from app.database.models import Material, MatchGroup, HarmonizedMaterial
        mat_cnt = db.query(Material).count()
        grp_cnt = db.query(MatchGroup).count()
        hm_cnt = db.query(HarmonizedMaterial).count()

        st.markdown(f"**Current Operational Records:** `{mat_cnt}` materials | `{grp_cnt}` match groups | `{hm_cnt}` harmonized CMCs")

        if user_role != "Admin":
            st.warning("Only users with the **Admin** role are authorized to clear operational database records.")
        else:
            confirm = st.checkbox("I confirm that I want to wipe all materials, inventory, match groups, and mappings.")
            if st.button("🗑️ Clear All Data (Reset to Empty)", type="primary", disabled=not confirm):
                from app.database.db import clear_all_data
                ok, msg = clear_all_data(db)
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ Error resetting database: {msg}")

