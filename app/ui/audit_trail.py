import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from app.database.models import AuditLog, MatchGroup, MatchGroupMember
from app.services.harmonization.review_service import undo_group_approval
from app.ui.auth import get_current_username, get_current_user_role
from app.utils.formatting import get_status_badge

def render_audit_trail_page(db: Session):
    st.title("Audit Trail & Traceability Ledger")
    st.caption("Immutable chronological record of all AI inferences, auto-approvals, officer reviews, and CPSE mappings")

    officer_name = get_current_username()
    user_role = get_current_user_role()

    tab_audit, tab_auto = st.tabs([
        "📜 Complete Audit Log",
        "🤖 Auto-Approved by AI (Safety Net & Re-open Review)"
    ])

    with tab_audit:
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()

        st.markdown(
            "> [!IMPORTANT]\n"
            "> **Traceability Guarantee:** Original CPSE legacy codes and descriptions are permanently immutable. "
            "> All harmonization decisions, automated approvals, and mapping associations are logged here with timestamps."
        )

        if not logs:
            st.info("No audit logs recorded yet. Ingest data or run harmonization to generate audit events.")
        else:
            c_actor, c_action = st.columns(2)
            with c_actor:
                actors = ["All Actors"] + sorted(list(set(l.actor for l in logs if l.actor)))
                sel_actor = st.selectbox("Filter Actor", actors)
            with c_action:
                actions = ["All Actions"] + sorted(list(set(l.action for l in logs if l.action)))
                sel_action = st.selectbox("Filter Action", actions)

            filtered_logs = logs
            if sel_actor != "All Actors":
                filtered_logs = [l for l in filtered_logs if l.actor == sel_actor]
            if sel_action != "All Actions":
                filtered_logs = [l for l in filtered_logs if l.action == sel_action]

            st.markdown(f"**Showing {len(filtered_logs)} audit records**")

            log_rows = []
            for log in filtered_logs:
                log_rows.append({
                    "Timestamp (UTC)": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "",
                    "Actor": log.actor,
                    "Action": log.action,
                    "Entity Type": log.entity_type,
                    "Entity ID": log.entity_id or "-",
                    "Details": log.details or ""
                })

            st.dataframe(pd.DataFrame(log_rows), use_container_width=True, hide_index=True)

    with tab_auto:
        st.subheader("AI Automated Approvals Safety Net")
        st.write(
            "Lists all material groups automatically approved by the AI engine based on high confidence "
            "(&ge; 95%) and strict exact/near duplicate criteria. Officers can audit the automated decisions and "
            "re-open any group for manual human review with full mapping rollback."
        )

        auto_groups = db.query(MatchGroup).filter(
            (MatchGroup.reviewed_by == "AI Auto-Approval") |
            (MatchGroup.status == "approved")
        ).order_by(MatchGroup.id.desc()).all()

        # Specifically focus on AI auto-approved groups
        auto_approved_groups = [g for g in auto_groups if g.reviewed_by == "AI Auto-Approval"]

        if not auto_approved_groups:
            st.info("No groups have been auto-approved by AI yet. Auto-approval runs automatically during AI Harmonization when confidence &ge; 95%.")
        else:
            st.markdown(f"**Total AI Auto-Approved Groups:** `{len(auto_approved_groups)}`")

            for grp in auto_approved_groups:
                members = [mem.material for mem in grp.members if mem.material]
                cmc = grp.harmonized_material.common_code if grp.harmonized_material else (grp.recommended_common_code or "Assigned")

                with st.container():
                    st.markdown(
                        f'<div style="background:#ffffff; color:#1f2937; border:1px solid #c2e7ff; border-radius:8px; padding:14px; margin-bottom:14px;">'
                        f'<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #f0f0f0; padding-bottom:8px; margin-bottom:8px;">'
                        f'<span style="font-weight:700; color:#1a365d; font-size:15px;">🏷️ Group #{grp.id} &mdash; Common Code: <code>{cmc}</code></span>'
                        f'<div>'
                        f'<span style="background:#e8f0fe; color:#1a73e8; padding:3px 8px; border-radius:12px; font-weight:600; font-size:12px; margin-right:8px;">Min Conf: {grp.group_min_confidence:.1f}%</span>'
                        f'{get_status_badge(grp.status)}'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                    c_mems, c_btn = st.columns([4, 1.5])
                    with c_mems:
                        mem_info = [f"<span style='color:#374151;'><b style='color:#111827;'>{m.cpse}:</b> <code style='color:#1e40af;'>{m.legacy_code}</code> ({m.raw_description})</span>" for m in members]
                        st.markdown("<br>".join(mem_info), unsafe_allow_html=True)
                        st.caption(f"Auto-approved at: {grp.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if grp.reviewed_at else 'Recently'}")

                    with c_btn:
                        if grp.status == "approved":
                            if user_role in ["Procurement Officer", "Admin"]:
                                if st.button("↩️ Undo & Re-open Review", key=f"undo_auto_{grp.id}", type="secondary", help="Unmaps materials and sends group back to pending review"):
                                    undo_group_approval(db, grp.id, officer_name=officer_name)
                                    st.warning(f"Group #{grp.id} re-opened for manual review.")
                                    st.rerun()
                            else:
                                st.caption("Switch role to Procurement Officer to undo.")
                        else:
                            st.info("Re-opened for review (Status: Pending)")

                    st.markdown('</div>', unsafe_allow_html=True)
