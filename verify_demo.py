import sys
import numpy as np
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database.db import SessionLocal, init_db
from app.database.models import Material, HarmonizedMaterial, MaterialMapping, MatchResult, AuditLog
from app.services.ingestion.demo_loader import load_demo_dataset
from app.services.matching.candidate_search import run_candidate_search_and_matching
from app.services.harmonization.review_service import approve_match
from app.services.embeddings.embedder import compute_embedding
from app.services.embeddings.vector_index import FaissVectorIndex
from app.services.analytics.inventory_analytics import get_harmonized_inventory_aggregation, compute_system_alerts
from app.services.analytics.financial_analytics import compute_financial_analytics
from app.ui.reports import evaluate_ai_accuracy_against_ground_truth

def run_verification():
    init_db()
    db = SessionLocal()

    print("=== 1. Loading Demo Dataset ===")
    ok, msg = load_demo_dataset(db)
    print("Result:", ok, msg)
    assert ok is True

    print("\n=== 2. Running AI Harmonization ===")
    matches = run_candidate_search_and_matching(db)
    print(f"Total Candidate Matches Found: {len(matches)}")
    assert len(matches) > 0

    print("\n=== 3. Inspecting High-Confidence Duplicate Match ===")
    high_conf = [m for m in matches if m.final_confidence >= 90.0]
    print(f"High-confidence matches count: {len(high_conf)}")
    top_match = high_conf[0]
    print(f"Top Pair: {top_match.material_a.cpse}:{top_match.material_a.legacy_code} vs {top_match.material_b.cpse}:{top_match.material_b.legacy_code}")
    print(f"Confidence: {top_match.final_confidence}% | Classification: {top_match.match_type}")
    print("AI Explanation:\n" + top_match.explanation_text)

    print("\n=== 4. Inspecting Specification Conflict Trap ===")
    conflicts = [m for m in matches if "Specification Conflict" in m.explanation_text]
    print(f"Specification Conflicts caught: {len(conflicts)}")
    assert len(conflicts) > 0
    for c in conflicts[:2]:
        print(f"Conflict: {c.material_a.legacy_code} vs {c.material_b.legacy_code} -> {c.match_type}")
        assert c.match_type == "SIMILAR_NOT_EQUIVALENT"

    print("\n=== 5. Approving Top Match & Generating CMC ===")
    h_mat = approve_match(db, top_match.id, officer_name="Chief Procurement Officer")
    print(f"Assigned Common Code: {h_mat.common_code}")
    print(f"Standard Description: {h_mat.standard_description}")
    print(f"Mapped CPSEs count: {len(h_mat.mappings)}")
    for m in h_mat.mappings:
        print(f" - {m.cpse} legacy code {m.legacy_code}")

    print("\n=== 6. Testing Semantic Search for 'SS bolt 16 50' ===")
    q_vec = compute_embedding("SS bolt 16 50")
    h_items = db.query(HarmonizedMaterial).all()
    h_texts = [f"{h.common_code} {h.standard_description} {h.material_type} {h.specification}" for h in h_items]
    h_vecs = np.array([compute_embedding(t) for t in h_texts], dtype=np.float32)
    idx = FaissVectorIndex(dimension=384)
    idx.add_materials([h.id for h in h_items], h_vecs)
    cands = idx.search(q_vec, top_k=1)
    print(f"Search Result: Matched Harmonized ID {cands[0][0]} with similarity {cands[0][1]*100:.1f}%")
    assert cands[0][0] == h_mat.id

    print("\n=== 7. Inventory Aggregation & Financial Analytics ===")
    agg = get_harmonized_inventory_aggregation(db)
    print(f"Aggregated Harmonized Materials: {len(agg)}")
    for item in agg:
        if item["harmonized_id"] == h_mat.id:
            print(f"Total Available Stock across CPSEs: {item['total_available']} {item['uom']}")
            print(f"CPSE breakdown: {item['cpse_breakdown']}")
            print(f"Duplicate stock flag: {item['is_duplicate_stock']}")

    fin = compute_financial_analytics(db)
    print(f"Total Inventory Value: INR {fin['total_inventory_value']:,.2f}")
    print(f"Duplicate Stock Value: INR {fin['duplicate_inventory_value']:,.2f}")
    print(f"Potential Working Capital Release: INR {fin['potential_working_capital_release']:,.2f}")
    print(f"Avoidable Procurement: INR {fin['avoidable_procurement_value']:,.2f}")

    print("\n=== 8. Offline Accuracy Evaluation vs Ground Truth ===")
    eval_res = evaluate_ai_accuracy_against_ground_truth(db)
    print("Evaluation Metrics:", eval_res["metrics"])

    print("\n=== 9. Audit Trail Verification ===")
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(6).all()
    for l in logs:
        print(f"[{l.timestamp.strftime('%H:%M:%S')}] {l.actor} -> {l.action} ({l.entity_type}): {l.details[:60]}...")

    print("\n=== ALL VERIFICATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_verification()
