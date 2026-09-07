import os
import sys

# Ensure app is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, ".."))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from app.database.db import SessionLocal
from app.database.models import Material, MatchResult, MatchGroup, MatchGroupMember
from app.services.matching.candidate_search import run_candidate_search_and_matching

def verify_dataset():
    db = SessionLocal()
    total_materials = db.query(Material).count()
    print(f"Total materials in database: {total_materials}")
    if total_materials == 0:
        print("No materials found in database.")
        return

    # Clean out previous results and re-run search & grouping
    print("Clearing old match results and groups...")
    db.query(MatchGroupMember).delete()
    db.query(MatchGroup).delete()
    db.query(MatchResult).delete()
    db.commit()

    print("Running candidate search, scoring, and multi-way grouping...")
    pairwise_count = run_candidate_search_and_matching(db)
    print(f"Candidate search complete. Pairwise matches created: {pairwise_count}")

    groups = db.query(MatchGroup).all()
    print(f"Total groups formed: {len(groups)}")
    statuses = {}
    for g in groups:
        statuses[g.status] = statuses.get(g.status, 0) + 1
    print(f"Group status distribution: {statuses}")

    # Check multi-CPSE bolt example and conflicting bolt
    print("\n--- Inspecting Bolt Clusters ---")
    bolt_materials = db.query(Material).filter(Material.raw_description.ilike("%M16%50%")).all()
    bolt_ids = [b.id for b in bolt_materials]
    print(f"M16 x 50mm Bolt materials found: {[b.legacy_code + ' (' + b.cpse + ')' for b in bolt_materials]}")

    # Check which groups these bolts belong to
    found_groups = set()
    for b in bolt_materials:
        member = db.query(MatchGroupMember).filter(MatchGroupMember.material_id == b.id).first()
        if member:
            found_groups.add(member.group_id)
            print(f"Material {b.legacy_code} ({b.cpse}) is in Group ID: {member.group_id}")
        else:
            print(f"Material {b.legacy_code} ({b.cpse}) is NOT in any group.")

    print(f"Distinct group IDs for M16 x 50mm bolts: {found_groups}")
    if len(found_groups) == 1:
        gid = list(found_groups)[0]
        grp = db.query(MatchGroup).get(gid)
        print(f"SUCCESS: All M16 x 50mm bolts collapsed into single Group {gid}!")
        print(f"Group {gid} Status: {grp.status}, Match Type: {grp.match_type}, Min Conf: {grp.group_min_confidence:.2f}%, Avg Conf: {grp.group_avg_confidence:.2f}%, Reviewed By: {grp.reviewed_by}")

    # Check conflicting 80mm bolt
    conflicting_bolts = db.query(Material).filter(Material.raw_description.ilike("%M16%80%")).all()
    print(f"\nConflicting M16 x 80mm Bolt materials: {[b.legacy_code + ' (' + b.cpse + ')' for b in conflicting_bolts]}")
    for cb in conflicting_bolts:
        member = db.query(MatchGroupMember).filter(MatchGroupMember.material_id == cb.id).first()
        if member:
            print(f"Material {cb.legacy_code} is in Group ID: {member.group_id}")
            if member.group_id in found_groups:
                print(f"ERROR: 80mm bolt is mistakenly merged into 50mm bolt group {member.group_id}!")
            else:
                print(f"SAFE: 80mm bolt is isolated in its own separate group {member.group_id}.")
        else:
            print(f"SAFE: 80mm bolt {cb.legacy_code} has no valid group (isolated).")

    db.close()

if __name__ == "__main__":
    verify_dataset()
