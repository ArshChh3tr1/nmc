import streamlit as st
import json
from sqlalchemy.orm import Session
from app.database.models import MatchGroup, MatchGroupMember, MatchResult, Material, HarmonizedMaterial, Category
from app.services.harmonization.review_service import approve_group, reject_group, undo_group_approval
from app.services.matching.candidate_search import run_candidate_search_and_matching
from app.services.matching.grouping import build_and_save_match_groups
from app.ui.auth import get_current_user_role, get_current_username
from app.utils.formatting import get_status_badge, format_pct

def render_harmonization_page(db: Session):
    st.title("AI Material Harmonization Review")
    st.caption("Review multi-CPSE candidate groups, inspect explainable AI pairwise evidence, and approve Common Material Codes (CMC)")

    user_role = get_current_user_role()
    officer_name = get_current_username()

    total_materials = db.query(Material).count()
    if total_materials == 0:
        st.info("No materials found in the database. Please load the demo dataset or upload your CPSE inventory spreadsheet to begin AI Harmonization.")
        return

    # If match_groups table is empty but match_results exist, cluster them automatically
    group_count = db.query(MatchGroup).count()
    if group_count == 0 and db.query(MatchResult).count() > 0:
        with st.spinner("Clustering existing pairwise matches into N-way groups..."):
            build_and_save_match_groups(db)

    # Filter controls
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        status_filter = st.selectbox("Filter Status", ["Pending", "Approved", "Rejected", "Modified", "All"], index=0)
    with col_f2:
        type_filter = st.selectbox("Match Classification", [
            "All Types", "EXACT_DUPLICATE", "NEAR_DUPLICATE", "FUNCTIONALLY_EQUIVALENT"
        ])
    with col_f3:
        sort_by = st.selectbox("Sort By", [
            "Min Confidence: High to Low", "Min Confidence: Low to High", "Member Count: High to Low", "Latest Created"
        ])

    query = db.query(MatchGroup)
    if status_filter != "All":
        query = query.filter(MatchGroup.status == status_filter.lower())
    if type_filter != "All Types":
        query = query.filter(MatchGroup.match_type == type_filter)

    if sort_by == "Min Confidence: High to Low":
        query = query.order_by(MatchGroup.group_min_confidence.desc())
    elif sort_by == "Min Confidence: Low to High":
        query = query.order_by(MatchGroup.group_min_confidence.asc())
    elif sort_by == "Member Count: High to Low":
        # Sort in memory after query
        pass
    else:
        query = query.order_by(MatchGroup.id.desc())

    groups = query.all()
    if sort_by == "Member Count: High to Low":
        groups = sorted(groups, key=lambda g: len(g.members), reverse=True)

    st.markdown(f"**Found {len(groups)} multi-CPSE candidate groups**")

    if not groups:
        st.info("No candidate groups match the current filter. Click 'Run AI Harmonization' to search and cluster materials.")
        if st.button("🚀 Run AI Harmonization Now", type="primary"):
            with st.spinner("Processing candidate search, attribute extraction, and N-way grouping..."):
                run_candidate_search_and_matching(db)
                st.success("Harmonization and grouping complete!")
                st.rerun()
        return

    for group in groups:
        members = [mem.material for mem in group.members if mem.material]
        if not members:
            continue

        member_ids = [m.id for m in members]

        # Retrieve underlying pairwise evidence edges
        pairwise_edges = []
        for i in range(len(member_ids)):
            for j in range(i + 1, len(member_ids)):
                p1, p2 = member_ids[i], member_ids[j]
                edge = db.query(MatchResult).filter(
                    ((MatchResult.material_a_id == p1) & (MatchResult.material_b_id == p2)) |
                    ((MatchResult.material_a_id == p2) & (MatchResult.material_b_id == p1))
                ).first()
                if edge:
                    pairwise_edges.append(edge)

        # Container card for each N-way group
        with st.container():
            auto_badge = '<span style="background:#e8f0fe; color:#1a73e8; border:1px solid #c2e7ff; padding:3px 8px; border-radius:12px; font-size:12px; font-weight:600; margin-right:8px;">🤖 Auto-Approved by AI</span>' if group.reviewed_by == "AI Auto-Approval" else ""

            reason_text = group.auto_approval_reason
            if not reason_text:
                if group.reviewed_by == "AI Auto-Approval":
                    reason_text = f"Auto-approved: Confidence {group.group_min_confidence:.1f}% >= 95.0% ({group.match_type.replace('_', ' ').title()})"
                elif group.match_type == "FUNCTIONALLY_EQUIVALENT":
                    reason_text = "Not auto-approved: Classified as Functionally Equivalent (requires engineering review)"
                else:
                    reason_text = f"Not auto-approved: Confidence {group.group_min_confidence:.1f}% is below threshold 95.0%"

            if group.reviewed_by == "AI Auto-Approval":
                reason_html = f'<div style="background:#e6f4ea; border-left:4px solid #137333; padding:8px 14px; border-radius:6px; margin-bottom:14px; font-size:13px; color:#137333;"><b>🤖 {reason_text}</b></div>'
            elif group.status == "pending":
                reason_html = f'<div style="background:#fef7e0; border-left:4px solid #f2994a; padding:8px 14px; border-radius:6px; margin-bottom:14px; font-size:13px; color:#b06000;"><b>📋 Review Requirement:</b> {reason_text}</div>'
            else:
                reason_html = f'<div style="background:#f1f3f4; border-left:4px solid #5f6368; padding:8px 14px; border-radius:6px; margin-bottom:14px; font-size:13px; color:#3c4043;"><b>Status:</b> {reason_text}</div>'

            st.markdown(
                f'<div style="background:#ffffff; color:#202124; border:1px solid #e0e0e0; border-radius:10px; padding:16px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">'
                f'<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #f0f0f0; padding-bottom:10px; margin-bottom:12px;">'
                f'<div>'
                f'<span style="font-size:16px; font-weight:700; color:#202124;">Candidate Group #{group.id} &mdash; {group.match_type}</span> '
                f'<span style="font-size:13px; color:#5f6368; margin-left:8px;">({len(members)} CPSE Materials)</span>'
                f'</div>'
                f'<div>'
                f'{auto_badge}'
                f'<span style="font-size:13px; font-weight:700; margin-right:8px; color:#1a73e8;" title="Gating score: minimum confidence of all links in group">Min Conf: {group.group_min_confidence:.1f}%</span>'
                f'<span style="font-size:12px; color:#5f6368; margin-right:12px;">(Avg: {group.group_avg_confidence:.1f}%)</span>'
                f'{get_status_badge(group.status)}'
                f'</div>'
                f'</div>'
                f'{reason_html}',
                unsafe_allow_html=True
            )

            # Render group members side-by-side (up to 3) or in a 2-column grid
            if len(members) <= 3:
                cols = st.columns(len(members))
                for idx, mat in enumerate(members):
                    letter = chr(65 + idx)
                    with cols[idx]:
                        st.markdown(
                            f'<div style="background:#f8f9fa; color:#202124; border:1px solid #dadce0; border-radius:8px; padding:12px; height:100%;">'
                            f'<div style="font-weight:700; color:#1a73e8; margin-bottom:4px;">🏛️ Source Material {letter} ({mat.cpse})</div>'
                            f'<div style="font-size:13px; font-weight:600; color:#202124;">Code: <code>{mat.legacy_code}</code></div>'
                            f'<div style="font-size:13px; margin:6px 0; color:#3c4043;"><b>Raw:</b> {mat.raw_description}</div>'
                            f'<div style="font-size:12px; color:#5f6368;"><b>Normalized:</b> {mat.normalized_description}</div>'
                            f'<div style="font-size:12px; color:#5f6368; margin-top:4px;"><b>Material:</b> {mat.material_type} | <b>Spec:</b> {mat.specification} | <b>UOM:</b> {mat.uom}</div>'
                            f'<div style="font-size:12px; color:#5f6368;"><b>Dimensions:</b> <code>{mat.dimensions_json}</code></div>'
                            f'<div style="font-size:12px; color:#137333; font-weight:600; margin-top:4px;">Unit Price: ₹{mat.unit_price:.2f}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
            else:
                # 2-column grid for 4+ members
                col1, col2 = st.columns(2)
                for idx, mat in enumerate(members):
                    target_col = col1 if idx % 2 == 0 else col2
                    letter = chr(65 + idx)
                    with target_col:
                        st.markdown(
                            f'<div style="background:#f8f9fa; color:#202124; border:1px solid #dadce0; border-radius:8px; padding:12px; margin-bottom:10px;">'
                            f'<div style="font-weight:700; color:#1a73e8; margin-bottom:4px;">🏛️ Source Material {letter} ({mat.cpse})</div>'
                            f'<div style="font-size:13px; font-weight:600; color:#202124;">Code: <code>{mat.legacy_code}</code></div>'
                            f'<div style="font-size:13px; margin:6px 0; color:#3c4043;"><b>Raw:</b> {mat.raw_description}</div>'
                            f'<div style="font-size:12px; color:#5f6368;"><b>Normalized:</b> {mat.normalized_description}</div>'
                            f'<div style="font-size:12px; color:#5f6368; margin-top:4px;"><b>Material:</b> {mat.material_type} | <b>Spec:</b> {mat.specification} | <b>UOM:</b> {mat.uom}</div>'
                            f'<div style="font-size:12px; color:#5f6368;"><b>Dimensions:</b> <code>{mat.dimensions_json}</code></div>'
                            f'<div style="font-size:12px; color:#137333; font-weight:600; margin-top:4px;">Unit Price: ₹{mat.unit_price:.2f}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

            # Recommended Common Material Code Banner
            rec_code = group.recommended_common_code or "NMC-GEN-0001"
            st.markdown(
                f'<div style="margin-top:12px; padding:8px 12px; background:#e6f4ea; border-radius:6px; font-size:13px; color:#137333;">'
                f'🏷️ <b>Recommended Common Material Code (CMC):</b> <code>{rec_code}</code> (Consolidates all {len(members)} CPSE records under one unified catalog code)'
                f'</div>',
                unsafe_allow_html=True
            )

            # Collapsible Pairwise AI Match Explanation Breakdown
            with st.expander(f"🔍 View AI Match Evidence & Pairwise Explanations ({len(pairwise_edges)} pair edges)", expanded=False):
                if not pairwise_edges:
                    st.caption("Group established through transitive graph connectivity.")
                for edge in pairwise_edges:
                    ma = edge.material_a
                    mb = edge.material_b
                    st.markdown(
                        f"**Edge:** `{ma.cpse}:{ma.legacy_code}` &harr; `{mb.cpse}:{mb.legacy_code}` &mdash; "
                        f"**Confidence:** `{edge.final_confidence:.1f}%` | **Tier:** `{edge.match_type}`"
                    )
                    st.code(edge.explanation_text, language="text")

            # Group Actions
            if user_role in ["Procurement Officer", "Admin"]:
                if group.status == "pending":
                    btn_col1, btn_col2, btn_col3 = st.columns([1.5, 1.5, 3])

                    with btn_col1:
                        if st.button(f"✅ Approve Group ({len(members)})", key=f"app_grp_{group.id}", type="primary"):
                            try:
                                h_mat = approve_group(db, group.id, officer_name=officer_name)
                                st.success(f"Group Approved! Assigned {h_mat.common_code} and linked all {len(members)} CPSE materials.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Approval failed: {str(e)}")

                    with btn_col2:
                        with st.popover("❌ Reject Group"):
                            st.write("**Reject Candidate Group**")
                            reason = st.text_area(
                                "Rejection Reason (Required)",
                                key=f"rej_grp_reason_{group.id}",
                                placeholder="e.g. Discrepancy in application requirements across facilities"
                            )
                            if st.button("Confirm Rejection", key=f"confirm_grp_rej_{group.id}"):
                                if not reason.strip():
                                    st.warning("Please enter a short rejection reason.")
                                else:
                                    reject_group(db, group.id, rejection_reason=reason, officer_name=officer_name)
                                    st.success("Group marked as Rejected.")
                                    st.rerun()

                    with btn_col3:
                        with st.popover("✏️ Modify & Approve Group"):
                            st.write("**Modify Standardized Attributes for Group**")
                            p_mat = members[0]
                            mod_desc = st.text_input("Standard Description", value=f"{p_mat.material_type} {p_mat.specification}".strip(), key=f"mod_grp_desc_{group.id}")
                            mod_type = st.text_input("Material", value=p_mat.material_type or "", key=f"mod_grp_type_{group.id}")
                            mod_spec = st.text_input("Specification", value=p_mat.specification or "", key=f"mod_grp_spec_{group.id}")
                            mod_dims = st.text_input("Dimensions JSON", value=p_mat.dimensions_json or "{}", key=f"mod_grp_dims_{group.id}")

                            if st.button("Approve Group with Modifications", key=f"mod_app_grp_{group.id}"):
                                mod_data = {
                                    "standard_description": mod_desc,
                                    "material_type": mod_type,
                                    "specification": mod_spec,
                                    "dimensions_json": mod_dims,
                                    "uom": p_mat.uom
                                }
                                h_mat = approve_group(db, group.id, officer_name=officer_name, modified_data=mod_data)
                                st.success(f"Modified & Approved! Assigned {h_mat.common_code} to all {len(members)} materials.")
                                st.rerun()

                else:
                    c_info, c_undo = st.columns([4, 2])
                    with c_info:
                        st.caption(f"Reviewed by **{group.reviewed_by or 'System'}** at {group.reviewed_at or 'N/A'}")
                    with c_undo:
                        if group.status in ["approved", "modified"]:
                            if st.button("↩️ Re-open for Review", key=f"undo_grp_{group.id}", help="Revokes approval, unmaps CPSE codes, and returns group to pending"):
                                undo_group_approval(db, group.id, officer_name=officer_name)
                                st.warning(f"Group #{group.id} re-opened for review.")
                                st.rerun()
            else:
                st.info("🔒 Review actions are disabled in Viewer mode. Switch to 'Procurement Officer' or 'Admin' in sidebar.")

            st.markdown('</div>', unsafe_allow_html=True)
