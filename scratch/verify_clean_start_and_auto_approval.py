import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.db import SessionLocal, init_db, clear_all_data
from app.database.models import Material, MatchGroup, MatchGroupMember, MatchResult, HarmonizedMaterial, Inventory
from app.services.ingestion.demo_loader import load_demo_dataset
from app.services.matching.candidate_search import run_candidate_search_and_matching

def test_flow():
    init_db()
    db = SessionLocal()
    print("=== Step 1: Clear All Data ===")
    clear_all_data(db)

    # Verify genuinely empty
    m_count = db.query(Material).count()
    g_count = db.query(MatchGroup).count()
    i_count = db.query(Inventory).count()
    r_count = db.query(MatchResult).count()
    h_count = db.query(HarmonizedMaterial).count()
    print(f"Empty check: Materials={m_count}, Groups={g_count}, Inventory={i_count}, MatchResults={r_count}, Harmonized={h_count}")
    assert m_count == 0
    assert g_count == 0
    assert i_count == 0

    print("\n=== Step 2: Manually Load Demo Dataset ===")
    ok, msg = load_demo_dataset(db)
    print(f"Load Demo Dataset Result: ok={ok}, msg={msg}")
    assert ok is True

    m_loaded = db.query(Material).count()
    print(f"Materials loaded: {m_loaded}")
    assert m_loaded > 0

    print("\n=== Step 3: Run AI Harmonization & Grouping ===")
    matches = run_candidate_search_and_matching(db)
    print(f"Pairwise candidates created: {len(matches)}")

    groups = db.query(MatchGroup).all()
    auto_approved = [g for g in groups if g.reviewed_by == "AI Auto-Approval"]
    pending = [g for g in groups if g.status == "pending"]

    print(f"\nTotal Match Groups: {len(groups)}")
    print(f"Auto-Approved Groups: {len(auto_approved)}")
    print(f"Pending Human Review Groups: {len(pending)}")

    for g in auto_approved:
        mems = [f"{m.material.cpse}:{m.material.legacy_code}" for m in g.members]
        print(f"Auto-approved Group #{g.id}: MinConf={g.group_min_confidence:.1f}%, Type={g.match_type}, Members={mems}, Reason='{g.auto_approval_reason}'")

    for g in pending:
        mems = [f"{m.material.cpse}:{m.material.legacy_code}" for m in g.members]
        print(f"Pending Group #{g.id}: MinConf={g.group_min_confidence:.1f}%, Type={g.match_type}, Members={mems}, Reason='{g.auto_approval_reason}'")

    print("\n=== Step 4: Verify Four-CPSE Bolt Group ===")
    four_bolt_codes = ["IO-FST-48392", "BP-FST-99213", "HP-FST-18372", "GA-FST-66291"]
    bolt_mats = db.query(Material).filter(Material.legacy_code.in_(four_bolt_codes)).all()
    print(f"Found {len(bolt_mats)} of 4 bolt materials in DB")
    assert len(bolt_mats) == 4

    bolt_group_ids = set()
    for bm in bolt_mats:
        mem = db.query(MatchGroupMember).filter(MatchGroupMember.material_id == bm.id).first()
        assert mem is not None, f"Material {bm.legacy_code} not found in any match group!"
        bolt_group_ids.add(mem.group_id)
        print(f" - {bm.cpse}:{bm.legacy_code} is in Group #{mem.group_id}")

    print(f"Distinct group IDs for the four bolts: {bolt_group_ids}")
    assert len(bolt_group_ids) == 1, f"Expected exactly 1 group for all 4 bolts, but got {bolt_group_ids}"

    bolt_grp_id = list(bolt_group_ids)[0]
    bolt_grp = db.query(MatchGroup).get(bolt_grp_id)
    print(f"\nFour-CPSE Bolt Group Details:")
    print(f"  Group ID: #{bolt_grp.id}")
    print(f"  Status: {bolt_grp.status}")
    print(f"  Reviewed By: {bolt_grp.reviewed_by}")
    print(f"  Match Type: {bolt_grp.match_type}")
    print(f"  Min Confidence: {bolt_grp.group_min_confidence:.1f}%")
    print(f"  Reason: {bolt_grp.auto_approval_reason}")

    assert bolt_grp.status == "approved", f"Expected group to be approved, got {bolt_grp.status}"
    assert bolt_grp.reviewed_by == "AI Auto-Approval", f"Expected reviewed_by to be 'AI Auto-Approval', got {bolt_grp.reviewed_by}"
    assert bolt_grp.group_min_confidence >= 95.0, f"Expected min confidence >= 95.0, got {bolt_grp.group_min_confidence}"

    print("\n=== Step 5: Verify Conflict Bolt Isolation (M16 x 80) ===")
    conflict_bolt = db.query(Material).filter(Material.legacy_code == "ON-FST-77182").first()
    assert conflict_bolt is not None
    mem_c = db.query(MatchGroupMember).filter(MatchGroupMember.material_id == conflict_bolt.id).first()
    if mem_c:
        assert mem_c.group_id != bolt_grp_id, f"Conflict bolt {conflict_bolt.legacy_code} was mistakenly added to 50mm bolt group #{bolt_grp_id}!"
        print(f"Conflict bolt {conflict_bolt.legacy_code} is isolated in its own group #{mem_c.group_id}.")
    else:
        print(f"Conflict bolt {conflict_bolt.legacy_code} is completely isolated (no group).")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
    db.close()

if __name__ == "__main__":
    test_flow()
