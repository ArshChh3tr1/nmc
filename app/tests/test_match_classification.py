import pytest
from app.services.matching.scorer import calculate_match_scores
from app.services.matching.classifier_match import classify_match

def test_dimension_conflict_prevents_duplicate_classification():
    # Identical except length: 50mm vs 80mm
    mat_50 = {
        "material": "Stainless Steel",
        "category": "Fasteners",
        "subcategory": "Hex Bolts",
        "specification": "ISO 4017",
        "dimensions": {"diameter_mm": 16.0, "length_mm": 50.0, "thread": "M16"},
        "uom": "NOS"
    }
    mat_80 = {
        "material": "Stainless Steel",
        "category": "Fasteners",
        "subcategory": "Hex Bolts",
        "specification": "ISO 4017",
        "dimensions": {"diameter_mm": 16.0, "length_mm": 80.0, "thread": "M16"},
        "uom": "NOS"
    }

    # Even with very high semantic similarity (0.95), the dimension conflict MUST force SIMILAR_NOT_EQUIVALENT
    scores = calculate_match_scores(semantic_similarity=0.95, mat_a_data=mat_50, mat_b_data=mat_80)
    assert scores["has_dimension_conflict"] is True
    assert "Length differs: 50.0mm vs 80.0mm" in scores["conflict_details"]

    match_type, desc = classify_match(scores)
    assert match_type == "SIMILAR_NOT_EQUIVALENT"
    assert "Specification Conflict" in desc
    assert match_type != "EXACT_DUPLICATE"
    assert match_type != "NEAR_DUPLICATE"
    assert match_type != "FUNCTIONALLY_EQUIVALENT"
