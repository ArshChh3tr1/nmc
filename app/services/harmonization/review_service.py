from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.database.models import Material, HarmonizedMaterial, MaterialMapping, MatchResult, MatchGroup, MatchGroupMember
from app.services.harmonization.code_generator import generate_common_material_code
from app.services.audit.audit_logger import log_action

def approve_match(
    db: Session,
    match_result_id: int,
    officer_name: str = "Procurement Officer",
    modified_data: Optional[Dict[str, Any]] = None
) -> HarmonizedMaterial:
    """
    Approves a candidate match, creating or updating the Common Material Code,
    linking the CPSE materials to material_mappings, setting match_results.status to approved,
    and recording immutable audit trail logs.
    Traceability guarantee: Original legacy codes and CPSE names in `materials` are strictly untouched.
    """
    match_result = db.query(MatchResult).filter(MatchResult.id == match_result_id).first()
    if not match_result:
        raise ValueError(f"MatchResult {match_result_id} not found.")

    mat_a = match_result.material_a
    mat_b = match_result.material_b

    # Check if either material is already mapped to an existing HarmonizedMaterial
    existing_mapping_a = db.query(MaterialMapping).filter(MaterialMapping.material_id == mat_a.id).first()
    existing_mapping_b = db.query(MaterialMapping).filter(MaterialMapping.material_id == mat_b.id).first()

    harmonized_material: Optional[HarmonizedMaterial] = None
    if existing_mapping_a:
        harmonized_material = existing_mapping_a.harmonized_material
    elif existing_mapping_b:
        harmonized_material = existing_mapping_b.harmonized_material

    # If neither is mapped yet, create a new HarmonizedMaterial
    if not harmonized_material:
        cat_abbrev = "FST"
        if mat_a.category and mat_a.category.abbrev:
            cat_abbrev = mat_a.category.abbrev
        elif mat_b.category and mat_b.category.abbrev:
            cat_abbrev = mat_b.category.abbrev

        new_code = generate_common_material_code(db, cat_abbrev)

        # Base description and attributes from modified_data or canonical material
        if modified_data:
            std_desc = modified_data.get("standard_description") or f"{mat_a.material_type} {mat_a.specification}".strip()
            cat_id = modified_data.get("category_id") or mat_a.category_id
            m_type = modified_data.get("material_type") or mat_a.material_type
            spec = modified_data.get("specification") or mat_a.specification
            dims_json = modified_data.get("dimensions_json") or mat_a.dimensions_json
            uom = modified_data.get("uom") or mat_a.uom
        else:
            std_desc = f"{mat_a.material_type or ''} {mat_a.specification or ''} - {mat_a.dimensions_json or ''}".strip()
            if not std_desc:
                std_desc = mat_a.normalized_description
            cat_id = mat_a.category_id or mat_b.category_id
            m_type = mat_a.material_type or mat_b.material_type
            spec = mat_a.specification or mat_b.specification
            dims_json = mat_a.dimensions_json or mat_b.dimensions_json
            uom = mat_a.uom or mat_b.uom

        harmonized_material = HarmonizedMaterial(
            common_code=new_code,
            standard_description=std_desc,
            category_id=cat_id,
            material_type=m_type,
            specification=spec,
            dimensions_json=dims_json,
            uom=uom,
            status="modified" if modified_data else "approved"
        )
        db.add(harmonized_material)
        db.flush()

        log_action(
            db=db,
            actor=officer_name,
            action="Common Material Code Generated",
            entity_type="HarmonizedMaterial",
            entity_id=harmonized_material.common_code,
            details=f"Generated code {harmonized_material.common_code} for standard description '{std_desc}'"
        )
    else:
        if modified_data:
            harmonized_material.status = "modified"

    # Now create material_mappings if they don't already exist
    materials_to_map = [mat_a, mat_b]
    for mat in materials_to_map:
        existing = db.query(MaterialMapping).filter(
            MaterialMapping.harmonized_material_id == harmonized_material.id,
            MaterialMapping.material_id == mat.id
        ).first()

        if not existing:
            mapping = MaterialMapping(
                harmonized_material_id=harmonized_material.id,
                material_id=mat.id,
                cpse=mat.cpse,
                legacy_code=mat.legacy_code,
                mapped_at=datetime.now(),
                mapped_by=officer_name
            )
            db.add(mapping)
            # Update status without touching legacy_code or cpse
            mat.status = "mapped"

            log_action(
                db=db,
                actor=officer_name,
                action="CPSE Mapping Created",
                entity_type="MaterialMapping",
                entity_id=f"{mat.cpse}:{mat.legacy_code}",
                details=f"Mapped {mat.cpse} legacy code '{mat.legacy_code}' to Common Code '{harmonized_material.common_code}'"
            )

    # Update MatchResult
    match_result.status = "modified" if modified_data else "approved"
    match_result.reviewed_by = officer_name
    match_result.reviewed_at = datetime.now()

    log_action(
        db=db,
        actor=officer_name,
        action="Match Approved" if not modified_data else "Match Modified and Approved",
        entity_type="MatchResult",
        entity_id=str(match_result.id),
        details=f"Confidence: {match_result.final_confidence}%, Type: {match_result.match_type}. Assigned {harmonized_material.common_code}"
    )

    db.commit()
    return harmonized_material

def reject_match(
    db: Session,
    match_result_id: int,
    rejection_reason: str,
    officer_name: str = "Procurement Officer"
) -> MatchResult:
    """
    Rejects a candidate match with a mandatory reason.
    No mapping is created; audit trail records the decision and reasoning.
    """
    match_result = db.query(MatchResult).filter(MatchResult.id == match_result_id).first()
    if not match_result:
        raise ValueError(f"MatchResult {match_result_id} not found.")

    match_result.status = "rejected"
    match_result.reviewed_by = officer_name
    match_result.reviewed_at = datetime.utcnow()

    log_action(
        db=db,
        actor=officer_name,
        action="Match Rejected",
        entity_type="MatchResult",
        entity_id=str(match_result.id),
        details=f"Rejection Reason: {rejection_reason.strip()}"
    )

    db.commit()
    return match_result

def approve_group(
    db: Session,
    group_id: int,
    officer_name: str = "Procurement Officer",
    modified_data: Optional[Dict[str, Any]] = None
) -> HarmonizedMaterial:
    """
    Approves an N-way material group in a single transaction:
    - Creates or updates the HarmonizedMaterial row.
    - Creates MaterialMapping rows for all group members.
    - Updates member materials to status='mapped'.
    - Updates MatchGroup and underlying pairwise MatchResults to status='approved' (or 'modified').
    - Records an audit log entry listing all CPSEs and codes involved.
    """
    group = db.query(MatchGroup).filter(MatchGroup.id == group_id).first()
    if not group:
        raise ValueError(f"MatchGroup {group_id} not found.")

    members = [mem.material for mem in group.members if mem.material]
    if not members:
        raise ValueError(f"MatchGroup {group_id} has no members.")

    harmonized_material: Optional[HarmonizedMaterial] = None
    for m in members:
        mapping = db.query(MaterialMapping).filter(MaterialMapping.material_id == m.id).first()
        if mapping and mapping.harmonized_material:
            harmonized_material = mapping.harmonized_material
            break

    primary_mat = members[0]

    if not harmonized_material:
        cat_abbrev = "GEN"
        for m in members:
            if m.category and m.category.abbrev:
                cat_abbrev = m.category.abbrev
                break

        new_code = group.recommended_common_code or generate_common_material_code(db, cat_abbrev)

        if modified_data:
            std_desc = modified_data.get("standard_description") or f"{primary_mat.material_type} {primary_mat.specification}".strip()
            cat_id = modified_data.get("category_id") or primary_mat.category_id
            m_type = modified_data.get("material_type") or primary_mat.material_type
            spec = modified_data.get("specification") or primary_mat.specification
            dims_json = modified_data.get("dimensions_json") or primary_mat.dimensions_json
            uom = modified_data.get("uom") or primary_mat.uom
        else:
            std_desc = f"{primary_mat.material_type or ''} {primary_mat.specification or ''} - {primary_mat.dimensions_json or ''}".strip()
            if not std_desc:
                std_desc = primary_mat.normalized_description or primary_mat.raw_description
            cat_id = primary_mat.category_id
            m_type = primary_mat.material_type
            spec = primary_mat.specification
            dims_json = primary_mat.dimensions_json
            uom = primary_mat.uom

        harmonized_material = HarmonizedMaterial(
            common_code=new_code,
            standard_description=std_desc,
            category_id=cat_id,
            material_type=m_type,
            specification=spec,
            dimensions_json=dims_json,
            uom=uom,
            status="modified" if modified_data else "approved"
        )
        db.add(harmonized_material)
        db.flush()
    else:
        if modified_data:
            harmonized_material.status = "modified"

    group.harmonized_material_id = harmonized_material.id

    # Create MaterialMapping for all group members in one atomic transaction
    mapped_cpse_codes = []
    for mat in members:
        existing = db.query(MaterialMapping).filter(
            MaterialMapping.harmonized_material_id == harmonized_material.id,
            MaterialMapping.material_id == mat.id
        ).first()

        if not existing:
            mapping = MaterialMapping(
                harmonized_material_id=harmonized_material.id,
                material_id=mat.id,
                cpse=mat.cpse,
                legacy_code=mat.legacy_code,
                mapped_at=datetime.utcnow(),
                mapped_by=officer_name
            )
            db.add(mapping)

        mat.status = "mapped"
        mapped_cpse_codes.append(f"{mat.cpse}:{mat.legacy_code}")

    group.status = "modified" if modified_data else "approved"
    group.reviewed_by = officer_name
    group.reviewed_at = datetime.utcnow()

    # Mark underlying pairwise MatchResults
    member_ids = [m.id for m in members]
    for i in range(len(member_ids)):
        for j in range(i + 1, len(member_ids)):
            p1, p2 = member_ids[i], member_ids[j]
            pairs = db.query(MatchResult).filter(
                ((MatchResult.material_a_id == p1) & (MatchResult.material_b_id == p2)) |
                ((MatchResult.material_a_id == p2) & (MatchResult.material_b_id == p1))
            ).all()
            for p in pairs:
                p.status = group.status
                p.reviewed_by = officer_name
                p.reviewed_at = datetime.utcnow()

    action_label = "AI Auto-Approval" if officer_name == "AI Auto-Approval" else ("Match Modified and Approved" if modified_data else "Match Approved")
    log_action(
        db=db,
        actor=officer_name,
        action=action_label,
        entity_type="MatchGroup",
        entity_id=str(group.id),
        details=f"Approved group #{group.id} ({len(members)} members: {', '.join(mapped_cpse_codes)}). Assigned {harmonized_material.common_code}. Min Conf: {group.group_min_confidence}%"
    )

    db.commit()
    return harmonized_material

def reject_group(
    db: Session,
    group_id: int,
    rejection_reason: str,
    officer_name: str = "Procurement Officer"
) -> MatchGroup:
    """Rejects an N-way candidate group with mandatory reason."""
    group = db.query(MatchGroup).filter(MatchGroup.id == group_id).first()
    if not group:
        raise ValueError(f"MatchGroup {group_id} not found.")

    group.status = "rejected"
    group.reviewed_by = officer_name
    group.reviewed_at = datetime.utcnow()
    group.rejection_reason = rejection_reason

    # Mark underlying pairwise MatchResults
    members = [mem.material for mem in group.members if mem.material]
    member_ids = [m.id for m in members]
    for i in range(len(member_ids)):
        for j in range(i + 1, len(member_ids)):
            p1, p2 = member_ids[i], member_ids[j]
            pairs = db.query(MatchResult).filter(
                ((MatchResult.material_a_id == p1) & (MatchResult.material_b_id == p2)) |
                ((MatchResult.material_a_id == p2) & (MatchResult.material_b_id == p1))
            ).all()
            for p in pairs:
                p.status = "rejected"
                p.reviewed_by = officer_name
                p.reviewed_at = datetime.utcnow()

    log_action(
        db=db,
        actor=officer_name,
        action="Match Rejected",
        entity_type="MatchGroup",
        entity_id=str(group.id),
        details=f"Rejected group #{group.id}. Reason: {rejection_reason.strip()}"
    )

    db.commit()
    return group

def undo_group_approval(
    db: Session,
    group_id: int,
    officer_name: str = "Procurement Officer"
) -> MatchGroup:
    """
    Re-opens an auto-approved or manually approved group for human review:
    - Sets group status to 'pending'.
    - Deletes material_mappings for all group members.
    - If the HarmonizedMaterial has no remaining mappings, deletes it.
    - Resets members' material status to 'processed'.
    - Resets underlying pairwise MatchResults to 'pending'.
    - Logs audit trail reversal.
    """
    group = db.query(MatchGroup).filter(MatchGroup.id == group_id).first()
    if not group:
        raise ValueError(f"MatchGroup {group_id} not found.")

    was_auto = (group.reviewed_by == "AI Auto-Approval")
    hm_id = group.harmonized_material_id

    members = [mem.material for mem in group.members if mem.material]
    member_ids = [m.id for m in members]

    if hm_id:
        db.query(MaterialMapping).filter(
            MaterialMapping.harmonized_material_id == hm_id,
            MaterialMapping.material_id.in_(member_ids)
        ).delete(synchronize_session=False)

        remaining = db.query(MaterialMapping).filter(
            MaterialMapping.harmonized_material_id == hm_id
        ).count()
        if remaining == 0:
            db.query(HarmonizedMaterial).filter(HarmonizedMaterial.id == hm_id).delete(synchronize_session=False)

    for m in members:
        m.status = "processed"

    group.status = "pending"
    group.reviewed_by = None
    group.reviewed_at = None
    group.harmonized_material_id = None

    for i in range(len(member_ids)):
        for j in range(i + 1, len(member_ids)):
            p1, p2 = member_ids[i], member_ids[j]
            pairs = db.query(MatchResult).filter(
                ((MatchResult.material_a_id == p1) & (MatchResult.material_b_id == p2)) |
                ((MatchResult.material_a_id == p2) & (MatchResult.material_b_id == p1))
            ).all()
            for p in pairs:
                p.status = "pending"
                p.reviewed_by = None
                p.reviewed_at = None

    log_action(
        db=db,
        actor=officer_name,
        action="AI Auto-Approval Revoked" if was_auto else "Group Approval Revoked",
        entity_type="MatchGroup",
        entity_id=str(group.id),
        details=f"Re-opened group #{group.id} ({len(members)} members) for review. Revoked mappings and reset status to pending."
    )

    db.commit()
    return group
