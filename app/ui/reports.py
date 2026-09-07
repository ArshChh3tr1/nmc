import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from app.config import DEMO_DATASET_PATH
from app.database.models import MatchResult, Material
from app.services.analytics.financial_analytics import compute_financial_analytics
from app.utils.formatting import format_inr, format_pct

def evaluate_ai_accuracy_against_ground_truth(db: Session):
    """
    Offline evaluation: Compares match_results against the demo workbook's Ground_Truth sheet.
    Computes True Positives, False Positives, True Negatives, False Negatives,
    Precision, Recall, F1-Score, and Specification Conflict Prevention Accuracy.
    NOTE: Ground_Truth sheet is NEVER read by the live matching pipeline itself.
    """
    if not DEMO_DATASET_PATH.exists():
        return None

    try:
        gt_df = pd.read_excel(DEMO_DATASET_PATH, sheet_name="Ground_Truth")
    except Exception:
        return None

    # Load all match results from DB
    matches = db.query(MatchResult).all()
    match_lookup = {}
    for m in matches:
        if m.material_a and m.material_b:
            pair = tuple(sorted([m.material_a.legacy_code, m.material_b.legacy_code]))
            match_lookup[pair] = m

    evaluation_rows = []
    tp = 0
    fp = 0
    fn = 0
    tn = 0
    conflict_detected = 0
    conflict_expected = 0

    for _, row in gt_df.iterrows():
        c_a = str(row.get("Material_A", "")).strip()
        c_b = str(row.get("Material_B", "")).strip()
        expected = str(row.get("Expected_Match", "")).strip()
        notes = str(row.get("Notes", "")).strip()
        pair = tuple(sorted([c_a, c_b]))

        m = match_lookup.get(pair)
        if m:
            pred_type = m.match_type
            conf = m.final_confidence
            has_conflict = "Specification Conflict" in m.explanation_text
        else:
            pred_type = "NO_MATCH"
            conf = 0.0
            has_conflict = False

        if expected in ["DUPLICATE", "EQUIVALENT"]:
            if pred_type in ["EXACT_DUPLICATE", "NEAR_DUPLICATE", "FUNCTIONALLY_EQUIVALENT"]:
                tp += 1
                result_verdict = "True Positive (Match Correct)"
            else:
                fn += 1
                result_verdict = "False Negative (Missed Match)"
        elif expected == "CONFLICT":
            conflict_expected += 1
            if has_conflict or pred_type == "SIMILAR_NOT_EQUIVALENT":
                tn += 1
                conflict_detected += 1
                result_verdict = "True Negative (Conflict Correctly Flagged)"
            else:
                fp += 1
                result_verdict = "False Positive (Failed to Catch Conflict)"
        else:
            if pred_type in ["EXACT_DUPLICATE", "NEAR_DUPLICATE", "FUNCTIONALLY_EQUIVALENT"]:
                fp += 1
                result_verdict = "False Positive (Erroneous Match)"
            else:
                tn += 1
                result_verdict = "True Negative (Correctly Rejected)"

        evaluation_rows.append({
            "Material A": c_a,
            "Material B": c_b,
            "Ground Truth": expected,
            "AI Prediction": pred_type,
            "Confidence": f"{conf:.1f}%",
            "Conflict Flagged": "YES" if has_conflict else "NO",
            "Evaluation Verdict": result_verdict,
            "Test Scenario": notes
        })

    precision = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 100.0
    recall = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 100.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 100.0
    conflict_acc = (conflict_detected / conflict_expected) * 100.0 if conflict_expected > 0 else 100.0

    return {
        "metrics": {
            "Precision": precision,
            "Recall": recall,
            "F1_Score": f1,
            "Conflict_Accuracy": conflict_acc,
            "True_Positives": tp,
            "False_Positives": fp,
            "False_Negatives": fn,
            "True_Negatives": tn
        },
        "details_df": pd.DataFrame(evaluation_rows)
    }

from app.services.export.export_service import generate_harmonized_materials_excel, build_harmonized_materials_dataframe

def render_reports_page(db: Session):
    header_col, export_col = st.columns([3, 1.5])
    with header_col:
        st.title("Audit & Analytics Reports")
        st.caption("Offline AI pipeline evaluation benchmarks, financial impact summaries, and master data export")

    with export_col:
        excel_bytes, export_filename, record_count = generate_harmonized_materials_excel(db)
        st.write("")
        st.download_button(
            label=f"📥 Download Harmonized Materials ({record_count})",
            data=excel_bytes,
            file_name=export_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=(record_count == 0),
            help="Download an Excel spreadsheet containing all approved/modified harmonized materials with CPSE mappings and inventory",
            use_container_width=True
        )

    tab_eval, tab_fin, tab_export = st.tabs([
        "🎯 AI Accuracy (Offline Evaluation vs Ground Truth)",
        "💰 Financial Impact & Savings Report",
        "📥 Harmonized Materials Export"
    ])

    with tab_eval:
        st.subheader("AI Accuracy & Validation Benchmarks (Ground Truth Evaluation)")
        st.markdown(
            "> [!NOTE]\n"
            "> **SIH Presentation Artifact:** This evaluation benchmarks the hybrid AI matching pipeline "
            "> (MiniLM Dense Embeddings + FAISS + Specification-Aware Scorer) against known CPSE test pairs, "
            "> including deliberate false-positive dimension traps (e.g. M16x50 vs M16x80).\n"
            "> *The Ground_Truth sheet is completely isolated and never accessed during live matching.*"
        )

        eval_result = evaluate_ai_accuracy_against_ground_truth(db)
        if db.query(Material).count() == 0:
            st.info("No materials loaded yet. Please load the demo dataset or upload data to begin.")
        elif db.query(MatchResult).count() == 0:
            st.info("No AI match results found in the database. Please load the demo dataset and click **🚀 Run AI Harmonization** to evaluate AI accuracy against ground truth.")
        elif not eval_result:
            st.info("Demo dataset or ground truth sheet not found. Load demo dataset from the Overview or Materials page.")
        else:
            m = eval_result["metrics"]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Model Precision", f"{m['Precision']:.1f}%")
            with col2:
                st.metric("Model Recall", f"{m['Recall']:.1f}%")
            with col3:
                st.metric("F1-Score", f"{m['F1_Score']:.1f}%")
            with col4:
                st.metric("Spec Conflict Detection", f"{m['Conflict_Accuracy']:.1f}%")

            st.markdown("### Ground Truth Evaluation Matrix")
            st.dataframe(eval_result["details_df"], use_container_width=True, hide_index=True)

    with tab_fin:
        if db.query(Material).count() == 0:
            st.info("No materials loaded yet. Please load the demo dataset or upload data to calculate financial savings.")
        else:
            st.subheader("Financial Impact & Avoidable Spend Summary")
            fin = compute_financial_analytics(db)

            st.markdown(
                f'<div style="background:#fef7e0; color:#78350f; border:1px solid #fde68a; border-left:4px solid #f9ab00; padding:10px 14px; border-radius:6px; margin-bottom:16px;">'
                f'<b style="color:#92400e;">{fin["disclaimer"]}</b><br>'
                f'<span style="color:#78350f;">Assumptions: Working Capital Release = {fin["assumptions"]["wc_release_pct"]:.0f}% of duplicate stock | '
                f'Avoidable Procurement = {fin["assumptions"]["avoidable_proc_pct"]:.0f}% | '
                f'Holding Cost Reduction = {fin["assumptions"]["holding_cost_pct"]:.0f}%</span>'
                f'</div>',
                unsafe_allow_html=True
            )

            r_col1, r_col2 = st.columns(2)
            with r_col1:
                st.metric("Total Enterprise Inventory Valuation", format_inr(fin["total_inventory_value"]))
                st.metric("Duplicate Inventory Valuation (Across CPSEs)", format_inr(fin["duplicate_inventory_value"]))
                st.metric("Potential Working Capital Release", format_inr(fin["potential_working_capital_release"]))

            with r_col2:
                st.metric("Estimated Avoidable Procurement Spend", format_inr(fin["avoidable_procurement_value"]))
                st.metric("Annual Carrying Cost Savings", format_inr(fin["annual_holding_cost_savings"]))
                st.metric("Total Potential Financial Benefit", format_inr(fin["total_potential_savings"]))

    with tab_export:
        st.subheader("Master Harmonized Materials Registry (.xlsx)")
        st.write(
            "Export all verified and approved Common Material Codes (CMCs), including unified specifications, "
            "attributes, mapped CPSE legacy material codes (IOCL, BPCL, HPCL, ONGC, GAIL), and consolidated enterprise stock."
        )

        export_df = build_harmonized_materials_dataframe(db)
        if export_df.empty:
            st.info("No approved harmonized materials are currently available to export. Approve candidate matches in the **AI Harmonization** tab first.")
        else:
            st.markdown(f"**Approved Harmonized Records:** `{len(export_df)}`")
            st.dataframe(export_df, use_container_width=True, hide_index=True)

            st.download_button(
                label=f"📥 Download Harmonized Materials Spreadsheet ({len(export_df)} items)",
                data=excel_bytes,
                file_name=export_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_report_export",
                help="Click to download approved materials formatted as an Excel workbook"
            )

