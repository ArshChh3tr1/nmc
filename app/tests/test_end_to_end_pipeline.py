import pytest
from app.database.db import SessionLocal, init_db
from app.database.models import Material, MatchResult
from app.services.ingestion.demo_loader import load_demo_dataset
from app.services.matching.candidate_search import run_candidate_search_and_matching
from app.services.harmonization.review_service import approve_match

def test_full_harmonization_pipeline_end_to_end():
    init_db()
    db = SessionLocal()
    try:
        # 1. Load demo dataset
        ok, msg = load_demo_dataset(db)
        assert ok is True

        # 2. Run harmonization matching
        matches = run_candidate_search_and_matching(db)
        assert len(matches) > 0

        # Assert at least one high-confidence match (>= 90%)
        high_conf_matches = [m for m in matches if m.final_confidence >= 90.0]
        assert len(high_conf_matches) > 0

        # Assert explainable output format
        top_match = high_conf_matches[0]
        assert "AI MATCH ANALYSIS" in top_match.explanation_text
        assert "FINAL CONFIDENCE" in top_match.explanation_text
        assert "RECOMMENDATION" in top_match.explanation_text

        # 3. Test approval workflow creates Common Material Code and MaterialMapping
        h_mat = approve_match(db, top_match.id, officer_name="Test Officer")
        assert h_mat.common_code.startswith("NMC-")
        assert len(h_mat.mappings) >= 2
        assert top_match.status == "approved"

    finally:
        db.close()
