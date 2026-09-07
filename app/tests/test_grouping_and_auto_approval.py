import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Material, MatchResult, MatchGroup, MatchGroupMember, HarmonizedMaterial, MaterialMapping
from app.services.matching.grouping import build_and_save_match_groups
from app.services.harmonization.review_service import approve_group, reject_group, undo_group_approval
from app.database.db import SessionLocal

def test_four_cpse_grouping_and_conflict_isolation():
    """
    Unit test on in-memory SQLite:
    - 4 CPSE identical bolts (IOCL, ONGC, BPCL, CPCL) with M16x50
    - 1 conflicting bolt (ONGC) with M16x80 (Specification Conflict)
    - Verifies 4 identical bolts collapse into 1 group and auto-approve
    - Verifies the 80mm bolt is NEVER pulled into the group
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create 4 identical bolts across CPSEs
    m_iocl = Material(cpse="IOCL", legacy_code="IO-BOLT-1", raw_description="HEX BOLT SS M16 X 50", normalized_description="hexagonal bolt stainless steel m16 x 50", material_type="Stainless Steel", specification="ISO 4017", dimensions_json='{"diameter_mm": 16.0, "length_mm": 50.0}', uom="NOS", status="processed")
    m_bpcl = Material(cpse="BPCL", legacy_code="BP-BOLT-2", raw_description="SS HEX HEAD BOLT 16X50", normalized_description="stainless steel hexagonal head bolt 16 x 50", material_type="Stainless Steel", specification="ISO 4017", dimensions_json='{"diameter_mm": 16.0, "length_mm": 50.0}', uom="NOS", status="processed")
    m_ongc = Material(cpse="ONGC", legacy_code="ON-BOLT-3", raw_description="STAINLESS STEEL BOLT M16-50", normalized_description="stainless steel bolt m16 - 50", material_type="Stainless Steel", specification="ISO 4017", dimensions_json='{"diameter_mm": 16.0, "length_mm": 50.0}', uom="NOS", status="processed")
    m_cpcl = Material(cpse="CPCL", legacy_code="CP-BOLT-4", raw_description="HEXAGONAL BOLT STL 16MM X 50MM", normalized_description="hexagonal bolt stainless steel 16 x 50", material_type="Stainless Steel", specification="ISO 4017", dimensions_json='{"diameter_mm": 16.0, "length_mm": 50.0}', uom="NOS", status="processed")

    # Conflicting bolt: 80mm length instead of 50mm
    m_conflict = Material(cpse="ONGC", legacy_code="ON-BOLT-80MM", raw_description="SS HEX BOLT M16 X 80", normalized_description="stainless steel hexagonal bolt m16 x 80", material_type="Stainless Steel", specification="ISO 4017", dimensions_json='{"diameter_mm": 16.0, "length_mm": 80.0}', uom="NOS", status="processed")

    db.add_all([m_iocl, m_bpcl, m_ongc, m_cpcl, m_conflict])
    db.commit()

    # Pairwise matches among the 4 matching bolts (high confidence EXACT_DUPLICATE)
    pair1 = MatchResult(material_a_id=m_iocl.id, material_b_id=m_bpcl.id, final_confidence=99.2, match_type="EXACT_DUPLICATE", explanation_text="Identical attributes", status="pending")
    pair2 = MatchResult(material_a_id=m_bpcl.id, material_b_id=m_ongc.id, final_confidence=98.5, match_type="EXACT_DUPLICATE", explanation_text="Identical attributes", status="pending")
    pair3 = MatchResult(material_a_id=m_ongc.id, material_b_id=m_cpcl.id, final_confidence=97.8, match_type="EXACT_DUPLICATE", explanation_text="Identical attributes", status="pending")

    # Conflicting pair: length discrepancy triggers SIMILAR_NOT_EQUIVALENT
    conflict_pair = MatchResult(material_a_id=m_iocl.id, material_b_id=m_conflict.id, final_confidence=65.0, match_type="SIMILAR_NOT_EQUIVALENT", explanation_text="Specification Conflict: length 50mm vs 80mm", status="pending")

    db.add_all([pair1, pair2, pair3, conflict_pair])
    db.commit()

    # Run Union-Find grouping and auto-approval
    groups = build_and_save_match_groups(db)

    # 1. Verify that the 4 materials collapsed into exactly 1 group
    assert len(groups) == 1
    grp = groups[0]
    member_mat_ids = [m.material_id for m in grp.members]
    assert len(member_mat_ids) == 4
    assert m_iocl.id in member_mat_ids
    assert m_bpcl.id in member_mat_ids
    assert m_ongc.id in member_mat_ids
    assert m_cpcl.id in member_mat_ids

    # 2. Verify that the 80mm conflicting bolt was NEVER included in the group
    assert m_conflict.id not in member_mat_ids

    # 3. Verify min confidence gating (min of 99.2, 98.5, 97.8 is 97.8)
    assert grp.group_min_confidence == 97.8
    assert grp.match_type == "EXACT_DUPLICATE"

    # 4. Verify AI Auto-Approval (97.8 >= 95.0)
    assert grp.status == "approved"
    assert grp.reviewed_by == "AI Auto-Approval"
    assert grp.harmonized_material_id is not None

    # Verify all 4 members have material_mappings
    mappings = db.query(MaterialMapping).filter(MaterialMapping.harmonized_material_id == grp.harmonized_material_id).all()
    assert len(mappings) == 4
    mapped_cpses = {mp.cpse for mp in mappings}
    assert mapped_cpses == {"IOCL", "BPCL", "ONGC", "CPCL"}

    # 5. Verify Undo / Re-open for Review
    undo_group_approval(db, grp.id, officer_name="Chief Procurement Officer")
    assert grp.status == "pending"
    assert grp.reviewed_by is None
    assert grp.harmonized_material_id is None

    # Verify mappings were revoked and materials reverted to processed
    revoked_mappings = db.query(MaterialMapping).filter(MaterialMapping.material_id.in_(member_mat_ids)).count()
    assert revoked_mappings == 0
    assert m_iocl.status == "processed"

    db.close()

def test_functionally_equivalent_never_auto_approved():
    """
    Verifies that groups with FUNCTIONALLY_EQUIVALENT are never auto-approved
    even if confidence is high, because human review is mandatory.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    m1 = Material(cpse="IOCL", legacy_code="M1", raw_description="BALL BEARING 6205", normalized_description="ball bearing 6205", material_type="Bearing", specification="ISO", dimensions_json='{"bore": 25}', uom="NOS", status="processed")
    m2 = Material(cpse="GAIL", legacy_code="M2", raw_description="DEEP GROOVE BEARING 6205 C3", normalized_description="deep groove ball bearing 6205 c3", material_type="Bearing", specification="ISO", dimensions_json='{"bore": 25}', uom="NOS", status="processed")
    db.add_all([m1, m2])
    db.commit()

    # Functionally equivalent pair with 96% confidence (> 95%)
    pair = MatchResult(material_a_id=m1.id, material_b_id=m2.id, final_confidence=96.5, match_type="FUNCTIONALLY_EQUIVALENT", explanation_text="Functionally equivalent clearance", status="pending")
    db.add(pair)
    db.commit()

    groups = build_and_save_match_groups(db)
    assert len(groups) == 1
    grp = groups[0]
    assert grp.match_type == "FUNCTIONALLY_EQUIVALENT"
    # Even though 96.5 >= 95.0, status must remain pending (no auto-approval)
    assert grp.status == "pending"
    assert grp.reviewed_by is None

    db.close()
