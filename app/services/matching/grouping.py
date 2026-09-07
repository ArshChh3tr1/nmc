from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
from sqlalchemy.orm import Session

from app.database.models import Material, MatchResult, MatchGroup, MatchGroupMember, Category
from app.services.harmonization.code_generator import generate_common_material_code
from app.config import get_weights_config

QUALIFYING_MATCH_TYPES = {"EXACT_DUPLICATE", "NEAR_DUPLICATE", "FUNCTIONALLY_EQUIVALENT"}

class UnionFind:
    """Disjoint Set Union (DSU) with path compression and rank optimization."""
    def __init__(self):
        self.parent: Dict[int, int] = {}
        self.rank: Dict[int, int] = {}

    def find(self, item: int) -> int:
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, x: int, y: int) -> None:
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x == root_y:
            return
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1

def build_and_save_match_groups(db: Session) -> List[MatchGroup]:
    """
    1. Clusters pairwise MatchResults into N-way connected components using Union-Find.
    2. Only edges with match_type in {EXACT_DUPLICATE, NEAR_DUPLICATE, FUNCTIONALLY_EQUIVALENT}
       are connected. SIMILAR_NOT_EQUIVALENT and NO_MATCH are strictly excluded.
    3. Computes group_min_confidence (the gating score) and group_avg_confidence.
    4. Persists MatchGroup and MatchGroupMember records.
    5. Performs AI Auto-Approval for groups whose group_min_confidence >= threshold
       and whose match_type is EXACT_DUPLICATE or NEAR_DUPLICATE.
    """
    # Import review_service lazily to prevent circular dependencies
    from app.services.harmonization.review_service import approve_group

    # Fetch all pending pairwise match results
    pending_matches = db.query(MatchResult).filter(MatchResult.status == "pending").all()
    if not pending_matches:
        return []

    # Clean up any existing unreviewed pending groups before rebuilding
    db.query(MatchGroupMember).filter(
        MatchGroupMember.group_id.in_(
            db.query(MatchGroup.id).filter(MatchGroup.status == "pending")
        )
    ).delete(synchronize_session=False)
    db.query(MatchGroup).filter(MatchGroup.status == "pending").delete(synchronize_session=False)
    db.flush()

    uf = UnionFind()
    qualifying_pairs: List[MatchResult] = []

    # Filter to qualifying edges only
    for match in pending_matches:
        if match.match_type in QUALIFYING_MATCH_TYPES:
            uf.union(match.material_a_id, match.material_b_id)
            qualifying_pairs.append(match)

    if not qualifying_pairs:
        return []

    # Group materials by their root component
    components: Dict[int, Set[int]] = defaultdict(set)
    for match in qualifying_pairs:
        root_a = uf.find(match.material_a_id)
        components[root_a].add(match.material_a_id)
        components[root_a].add(match.material_b_id)

    # Load auto-approve settings from config
    cfg = get_weights_config()
    auto_approve_cfg = cfg.get("auto_approve", {"enabled": True, "threshold": 95.0})
    auto_approve_enabled = auto_approve_cfg.get("enabled", True)
    auto_approve_threshold = float(auto_approve_cfg.get("threshold", 95.0))

    created_groups: List[MatchGroup] = []

    # Fast lookup for pairwise match edges
    pair_map: Dict[Tuple[int, int], MatchResult] = {}
    for match in pending_matches:
        pair_key = tuple(sorted([match.material_a_id, match.material_b_id]))
        pair_map[pair_key] = match

    for root_id, member_ids in components.items():
        if len(member_ids) < 2:
            continue

        # Find all qualifying pairwise edges within this component
        member_list = sorted(list(member_ids))
        edges: List[MatchResult] = []
        for i in range(len(member_list)):
            for j in range(i + 1, len(member_list)):
                key = (member_list[i], member_list[j])
                if key in pair_map:
                    edge = pair_map[key]
                    if edge.match_type in QUALIFYING_MATCH_TYPES:
                        edges.append(edge)

        if not edges:
            continue

        # Calculate group-level metrics
        min_conf = min(e.final_confidence for e in edges)
        avg_conf = sum(e.final_confidence for e in edges) / len(edges)

        # Conservative match tier resolution across group edges
        if any(e.match_type == "FUNCTIONALLY_EQUIVALENT" for e in edges):
            grp_match_type = "FUNCTIONALLY_EQUIVALENT"
        elif any(e.match_type == "NEAR_DUPLICATE" for e in edges):
            grp_match_type = "NEAR_DUPLICATE"
        else:
            grp_match_type = "EXACT_DUPLICATE"

        # Determine category code for recommended CMC
        members = db.query(Material).filter(Material.id.in_(member_list)).all()
        cat_abbrev = "GEN"
        for m in members:
            if m.category and m.category.abbrev:
                cat_abbrev = m.category.abbrev
                break

        rec_cmc = generate_common_material_code(db, cat_abbrev)

        # Create MatchGroup record
        group = MatchGroup(
            group_min_confidence=round(min_conf, 2),
            group_avg_confidence=round(avg_conf, 2),
            match_type=grp_match_type,
            status="pending",
            recommended_common_code=rec_cmc
        )
        db.add(group)
        db.flush()

        # Add MatchGroupMember records
        for mat_id in member_list:
            member_obj = MatchGroupMember(group_id=group.id, material_id=mat_id)
            db.add(member_obj)

        db.flush()

        # Check AI Auto-Approval conditions:
        # 1. auto_approve_enabled == True
        # 2. group_min_confidence >= auto_approve_threshold
        # 3. match_type is EXACT_DUPLICATE or NEAR_DUPLICATE (never FUNCTIONALLY_EQUIVALENT)
        if not auto_approve_enabled:
            reason = "Not auto-approved: AI Auto-Approval is disabled in Settings"
        elif group.match_type == "FUNCTIONALLY_EQUIVALENT":
            reason = "Not auto-approved: Classified as Functionally Equivalent (requires engineering review)"
        elif group.group_min_confidence < auto_approve_threshold:
            reason = f"Not auto-approved: Confidence {group.group_min_confidence:.1f}% is below threshold {auto_approve_threshold:.1f}%"
        else:
            reason = f"Auto-approved: Confidence {group.group_min_confidence:.1f}% >= threshold {auto_approve_threshold:.1f}% ({group.match_type.replace('_', ' ').title()})"

        group.auto_approval_reason = reason

        should_auto_approve = (
            auto_approve_enabled and
            group.group_min_confidence >= auto_approve_threshold and
            group.match_type in {"EXACT_DUPLICATE", "NEAR_DUPLICATE"}
        )

        if should_auto_approve:
            approve_group(db, group.id, officer_name="AI Auto-Approval")

        created_groups.append(group)

    db.commit()
    return created_groups
