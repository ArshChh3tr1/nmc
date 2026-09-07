import io
import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.database.models import Material, HarmonizedMaterial, MaterialMapping, Category, Inventory
from app.services.embeddings.embedder import compute_embedding
from app.services.embeddings.vector_index import FaissVectorIndex
from app.utils.formatting import get_status_badge, format_inr
from app.services.ingestion.demo_loader import load_demo_dataset
from app.services.ingestion.file_loader import ingest_material_file
from app.utils.validators import validate_dataframe, EXPECTED_COLUMNS
from app.services.export.export_service import generate_harmonized_materials_excel
from app.services.matching.candidate_search import run_candidate_search_and_matching
from app.ui.auth import get_current_username

def get_sample_template_bytes() -> bytes:
    """Returns an in-memory sample Excel template with all 16 expected columns."""
    sample_rows = [
        {
            "CPSE": "IOCL",
            "Legacy Material Code": "IO-VAL-90210",
            "Raw Material Description": "GATE VALVE CS FLANGED CLASS 150 50MM",
            "Category": "Valves",
            "Subcategory": "Gate Valves",
            "Material": "Carbon Steel",
            "Specification": "API 600",
            "Dimensions": '{"diameter_mm": 50, "rating": "150#"}',
            "UOM": "NOS",
            "Unit Price": 4200.0,
            "Available Quantity": 45.0,
            "Reserved Quantity": 10.0,
            "On Order Quantity": 20.0,
            "Reorder Level": 15.0,
            "Warehouse": "IOCL Panipat Refinery Store",
            "Supplier": "L&T Valves Limited"
        },
        {
            "CPSE": "BPCL",
            "Legacy Material Code": "BP-VAL-33412",
            "Raw Material Description": "CS GATE VALVE FLANGED #150 2 INCH",
            "Category": "Valves",
            "Subcategory": "Gate Valves",
            "Material": "Carbon Steel",
            "Specification": "API 600",
            "Dimensions": '{"diameter_mm": 50, "rating": "150#"}',
            "UOM": "NOS",
            "Unit Price": 4150.0,
            "Available Quantity": 30.0,
            "Reserved Quantity": 5.0,
            "On Order Quantity": 10.0,
            "Reorder Level": 12.0,
            "Warehouse": "BPCL Mumbai Refinery Store",
            "Supplier": "Flowserve India"
        }
    ]
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame(sample_rows).to_excel(writer, index=False, sheet_name="Material_Master")
    bio.seek(0)
    return bio.getvalue()

def render_relationship_tree(hm: HarmonizedMaterial):
    """
    Renders a clean, card-based branching visualization:
    Common Code -> CPSEs and their Legacy Codes
    """
    mappings = hm.mappings
    if not mappings:
        return

    st.markdown(
        f'<div style="background:#f1f3f4; color:#202124; padding:16px; border-radius:10px; text-align:center; margin:16px 0;">'
        f'<div style="display:inline-block; background:#1a73e8; color:white; padding:8px 20px; border-radius:8px; font-weight:700; font-size:16px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">'
        f'🏷️ {hm.common_code} &mdash; {hm.standard_description}'
        f'</div>'
        f'<div style="font-size:20px; color:#5f6368; margin:6px 0;">│<br>┌─────────────────┴─────────────────┐</div>'
        f'<div style="display:flex; justify-content:center; gap:20px; flex-wrap:wrap;">',
        unsafe_allow_html=True
    )

    cols = st.columns(len(mappings))
    for idx, mapping in enumerate(mappings):
        mat = mapping.material
        with cols[idx]:
            st.markdown(
                f'<div style="background:white; border:1px solid #dadce0; border-radius:8px; padding:12px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05);">'
                f'<div style="font-weight:700; font-size:14px; color:#202124;">🏛️ {mapping.cpse}</div>'
                f'<div style="font-size:13px; color:#1a73e8; font-weight:600; margin:4px 0;"><code>{mapping.legacy_code}</code></div>'
                f'<div style="font-size:12px; color:#5f6368;">{mat.raw_description if mat else ""}</div>'
                f'<div style="font-size:11px; color:#137333; font-weight:600; margin-top:6px;">Mapped: {mapping.mapped_at.strftime("%Y-%m-%d") if mapping.mapped_at else "Recently"}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown('</div>', unsafe_allow_html=True)

def render_materials_page(db: Session):
    header_col, export_col = st.columns([3, 1.5])
    with header_col:
        st.title("Material Explorer & Common Code Repository")
        st.caption("Browse CPSE materials, search using natural language semantics, and view Common Material Code relationships")
    
    with export_col:
        excel_bytes, export_filename, record_count = generate_harmonized_materials_excel(db)
        st.write("") # spacing
        st.download_button(
            label=f"📥 Download Harmonized Materials ({record_count})",
            data=excel_bytes,
            file_name=export_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=(record_count == 0),
            help="Download an Excel spreadsheet containing all approved/modified harmonized materials with CPSE mappings and inventory",
            use_container_width=True
        )

    tab_import, tab_search, tab_browse, tab_tree = st.tabs([
        "📥 Data Ingestion & Import",
        "🔍 Natural Language Semantic Search",
        "📋 Material Master Table",
        "🌳 Material Relationship Hierarchy"
    ])

    # Tab 1: Data Ingestion & Import
    with tab_import:
        st.subheader("Material Data Source & Batch Ingestion")
        st.write("Choose whether to load the synthetic multi-CPSE benchmark dataset or upload your own enterprise material master workbook.")

        data_choice = st.radio(
            "Select Data Ingestion Mode",
            ["Use Demo Dataset", "Upload My Own Data"],
            horizontal=True,
            index=1
        )

        st.markdown("---")

        if data_choice == "Use Demo Dataset":
            st.markdown("#### 🏛️ Synthetic Multi-CPSE Benchmark Dataset")
            st.info(
                "The built-in demo dataset includes 17 carefully curated materials across **IOCL, BPCL, HPCL, ONGC, and GAIL**. "
                "It features identical duplicate bolts, equivalent bearings, intentional dimension traps (M16x50 vs M16x80), "
                "and full multi-warehouse inventory values for SIH presentation testing."
            )
            col_demo, _ = st.columns([2, 4])
            with col_demo:
                if st.button("📥 Load Demo Dataset", type="primary", use_container_width=True):
                    with st.spinner("Loading synthetic CPSE dataset..."):
                        ok, msg = load_demo_dataset(db, actor_name=get_current_username())
                        if ok:
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

        else:
            st.markdown("#### 📤 Custom CPSE Data Upload (.xlsx / .csv)")
            st.caption("Upload material master records for ingestion into the harmonizer repository.")

            # Expected columns guidance and template download
            col_info_box, col_tmpl_btn = st.columns([3, 1])
            with col_info_box:
                st.markdown(
                    "<div style='font-size:13px; color:#4a5568; background:#f7fafc; padding:10px; border-radius:6px; border:1px solid #e2e8f0;'>"
                    "<b>Required Columns (16):</b> <code>" + ", ".join(EXPECTED_COLUMNS) + "</code>"
                    "</div>",
                    unsafe_allow_html=True
                )
            with col_tmpl_btn:
                st.download_button(
                    label="📄 Download Sample Template (.xlsx)",
                    data=get_sample_template_bytes(),
                    file_name="sample_cpse_material_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    help="Download preformatted Excel template with required columns"
                )

            st.write("")
            uploaded_file = st.file_uploader(
                "Upload CPSE Material Master Spreadsheet",
                type=["xlsx", "csv"],
                help="Accepts Microsoft Excel (.xlsx) and Comma-Separated Values (.csv) formats"
            )

            if uploaded_file is not None:
                file_bytes = uploaded_file.getvalue()
                try:
                    if uploaded_file.name.lower().endswith(".csv"):
                        raw_df = pd.read_csv(io.BytesIO(file_bytes))
                    else:
                        raw_df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)

                    # Validate DataFrame against all 16 expected columns
                    cleaned_df, report = validate_dataframe(raw_df, check_all_expected=True)

                    if report["errors"]:
                        st.error(f"❌ **Validation Failed:** {report['errors'][0]}")
                        if report.get("missing_columns"):
                            st.warning(f"Missing expected columns: **{', '.join(report['missing_columns'])}**")
                    else:
                        st.success("✅ **File Schema Validated Successfully!** All expected columns are present.")

                        # Summary metric cards
                        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                        with m_col1:
                            st.metric("Total Rows Loaded", report["records_loaded"])
                        with m_col2:
                            st.metric("Valid Rows", report["valid_records"])
                        with m_col3:
                            st.metric("Missing Non-Critical Fields", report["missing_fields"])
                        with m_col4:
                            st.metric("Duplicate Rows", report["duplicate_rows"])

                        if report["warnings"]:
                            with st.expander(f"⚠️ Validation Warnings & Skipped Rows ({len(report['warnings'])})", expanded=False):
                                for warn in report["warnings"]:
                                    st.write(f"- {warn}")

                        st.write("##### Data Preview (First 5 Valid Records)")
                        st.dataframe(cleaned_df.head(5), use_container_width=True, hide_index=True)

                        col_ingest, col_harmonize = st.columns([2, 2])
                        with col_ingest:
                            if st.button("💾 Ingest Records into Database", type="primary", use_container_width=True):
                                with st.spinner("Ingesting materials, extracting attributes, and building inventory records..."):
                                    ok, ing_report = ingest_material_file(
                                        db=db,
                                        file_bytes_or_path=file_bytes,
                                        file_name=uploaded_file.name,
                                        actor_name=get_current_username(),
                                        check_all_expected=True
                                    )
                                    if ok:
                                        st.success(
                                            f"🎉 **Ingestion Successful!** Added **{ing_report.get('new_materials', 0)}** new materials "
                                            f"({ing_report.get('existing_materials', 0)} already existing). "
                                            f"Newly loaded records are now ready for AI Harmonization!"
                                        )
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Ingestion failed: {ing_report.get('errors', ['Unknown error'])[0]}")

                        with col_harmonize:
                            if st.button("🚀 Run AI Harmonization Now", help="Run normalization, embeddings, and candidate matching", use_container_width=True):
                                with st.spinner("Running candidate search and matching pipeline..."):
                                    matches = run_candidate_search_and_matching(db)
                                    st.success(f"Harmonization complete! Generated {len(matches)} candidate matches.")
                                    st.rerun()

                except Exception as ex:
                    st.error(f"❌ Could not process uploaded file: {str(ex)}")

    # Tab 2: Natural Language Semantic Search
    with tab_search:
        st.subheader("Semantic Material Search (FAISS + MiniLM)")
        st.write("Search materials in plain conversational language (e.g. *\"stainless steel bolt 16mm 50mm\"* or *\"I need a 6205 bearing\"*).")

        query_text = st.text_input(
            "Search Query",
            placeholder="Type material requirement, specifications, or dimensions...",
            value=""
        )

        if query_text.strip():
            with st.spinner("Searching semantic vector index..."):
                query_vec = compute_embedding(query_text)

                # Search Harmonized Materials first
                harmonized_items = db.query(HarmonizedMaterial).all()
                results_found = False

                if harmonized_items:
                    h_texts = [f"{h.common_code} {h.standard_description} {h.material_type} {h.specification} {h.dimensions_json}" for h in harmonized_items]
                    h_vecs = np.array([compute_embedding(t) for t in h_texts], dtype=np.float32)
                    
                    h_index = FaissVectorIndex(dimension=384)
                    h_index.add_materials([h.id for h in harmonized_items], h_vecs)
                    h_candidates = h_index.search(query_vec, top_k=5)

                    if h_candidates and h_candidates[0][1] >= 0.45:
                        results_found = True
                        st.markdown(f"### Harmonized Material Matches ({len(h_candidates)} found)")
                        for h_id, score in h_candidates:
                            hm = next(x for x in harmonized_items if x.id == h_id)
                            st.markdown(
                                f'<div style="background:#ffffff; color:#1f2937; border:1px solid #c2e7ff; border-radius:8px; padding:16px; margin-bottom:12px;">'
                                f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                                f'<span style="font-size:16px; font-weight:700; color:#1a73e8;">🏷️ {hm.common_code} &mdash; {hm.standard_description}</span>'
                                f'<span style="background:#e8f0fe; color:#1a73e8; padding:3px 10px; border-radius:12px; font-weight:600; font-size:12px;">Semantic Match: {score*100:.1f}%</span>'
                                f'</div>'
                                f'<div style="margin:8px 0; font-size:13px; color:#3c4043;">'
                                f'<b>Category:</b> {hm.category.name if hm.category else "N/A"} | <b>Material:</b> {hm.material_type} | <b>Spec:</b> {hm.specification} | <b>Dimensions:</b> <code>{hm.dimensions_json}</code>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

                            # Mapped CPSE materials and warehouses
                            if hm.mappings:
                                st.write("**Mapped CPSE Holdings:**")
                                mapping_rows = []
                                for m in hm.mappings:
                                    mat = m.material
                                    invs = mat.inventories if mat else []
                                    tot_avail = sum(i.available_qty for i in invs)
                                    whs = ", ".join(i.warehouse.name for i in invs if i.warehouse)
                                    mapping_rows.append({
                                        "CPSE": m.cpse,
                                        "Legacy Code": m.legacy_code,
                                        "Description": mat.raw_description if mat else "",
                                        "Available Stock": f"{tot_avail} {mat.uom if mat else ''}",
                                        "Unit Price": format_inr(mat.unit_price) if mat else "₹0",
                                        "Warehouses": whs or "Central Store"
                                    })
                                st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True, hide_index=True)

                            st.markdown('</div>', unsafe_allow_html=True)

                # If no strong harmonized match, search raw materials
                if not results_found:
                    materials = db.query(Material).all()
                    if materials:
                        m_texts = [f"{m.raw_description} {m.normalized_description} {m.material_type} {m.specification} {m.dimensions_json}" for m in materials]
                        m_vecs = np.array([compute_embedding(t) for t in m_texts], dtype=np.float32)
                        m_index = FaissVectorIndex(dimension=384)
                        m_index.add_materials([m.id for m in materials], m_vecs)
                        m_candidates = m_index.search(query_vec, top_k=5)

                        st.markdown("### Raw Material Candidates (Not yet harmonized)")
                        for m_id, score in m_candidates:
                            mat = next(x for x in materials if x.id == m_id)
                            st.markdown(
                                f'<div style="background:#f8f9fa; color:#202124; border:1px solid #dadce0; border-radius:8px; padding:12px; margin-bottom:10px;">'
                                f'<b style="color:#111827;">{mat.cpse}</b> &mdash; <code style="color:#1e3a8a;">{mat.legacy_code}</code>: {mat.raw_description}<br>'
                                f'<span style="font-size:12px; color:#5f6368;">Score: {score*100:.1f}% | Material: {mat.material_type} | Spec: {mat.specification} | Dims: {mat.dimensions_json}</span>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

    # Tab 3: Material Master Table
    with tab_browse:
        st.subheader("All Material Records")

        if db.query(Material).count() == 0:
            st.info("No materials found in the master registry. Please load the demo dataset or upload a file via the '📥 Data Ingestion & Import' tab above to populate the catalog.")
            return

        # Filters
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            all_cpses = ["All"] + sorted(list(set(m.cpse for m in db.query(Material.cpse).distinct())))
            sel_cpse = st.selectbox("CPSE", all_cpses)
        with f_col2:
            all_cats = ["All"] + sorted(list(set(c.name for c in db.query(Category.name).distinct())))
            sel_cat = st.selectbox("Category", all_cats)
        with f_col3:
            sel_status = st.selectbox("Status", ["All", "raw", "processed", "mapped"])
        with f_col4:
            search_code = st.text_input("Filter Code / Text", placeholder="Search keyword...")

        q = db.query(Material)
        if sel_cpse != "All":
            q = q.filter(Material.cpse == sel_cpse)
        if sel_cat != "All":
            q = q.join(Category).filter(Category.name == sel_cat)
        if sel_status != "All":
            q = q.filter(Material.status == sel_status)
        if search_code.strip():
            sc = f"%{search_code.strip()}%"
            q = q.filter(
                (Material.legacy_code.like(sc)) |
                (Material.raw_description.like(sc)) |
                (Material.normalized_description.like(sc))
            )

        mat_list = q.all()
        table_data = []
        for m in mat_list:
            mapping = db.query(MaterialMapping).filter(MaterialMapping.material_id == m.id).first()
            cmc = mapping.harmonized_material.common_code if mapping and mapping.harmonized_material else "Unmapped"
            table_data.append({
                "CPSE": m.cpse,
                "Legacy Code": m.legacy_code,
                "Common Material Code": cmc,
                "Raw Description": m.raw_description,
                "Material": m.material_type or "",
                "Specification": m.specification or "",
                "Dimensions": m.dimensions_json or "",
                "UOM": m.uom or "",
                "Unit Price": format_inr(m.unit_price),
                "Status": m.status
            })

        if table_data:
            st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
        else:
            st.info("No materials found matching criteria.")

    # Tab 4: Relationship Hierarchy
    with tab_tree:
        st.subheader("Common Material Code (CMC) Branching View")
        harmonized = db.query(HarmonizedMaterial).all()
        if not harmonized:
            st.info("No materials have been harmonized yet. Review matches in the 'AI Harmonization' tab to generate Common Material Codes.")
        else:
            sel_hm_code = st.selectbox(
                "Select Harmonized Material to Inspect Hierarchy",
                [f"{h.common_code} - {h.standard_description}" for h in harmonized]
            )
            hm_code = sel_hm_code.split(" - ")[0]
            hm_obj = db.query(HarmonizedMaterial).filter(HarmonizedMaterial.common_code == hm_code).first()
            if hm_obj:
                render_relationship_tree(hm_obj)
