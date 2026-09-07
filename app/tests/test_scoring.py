import pytest
from app.services.matching.scorer import calculate_match_scores
from app.config import get_weights_config

def test_weighted_scoring_math():
    cfg = get_weights_config()
    weights = cfg["weights"]
    assert "semantic_similarity" in weights
    assert "material_match" in weights
    assert "dimension_match" in weights

    mat_a = {
        "material": "Stainless Steel",
        "category": "Fasteners",
        "subcategory": "Hex Bolts",
        "specification": "ISO 4017",
        "dimensions": {"diameter_mm": 16.0, "length_mm": 50.0, "thread": "M16"},
        "uom": "NOS"
    }
    mat_b = {
        "material": "Stainless Steel",
        "category": "Fasteners",
        "subcategory": "Hex Bolts",
        "specification": "ISO 4017",
        "dimensions": {"diameter_mm": 16.0, "length_mm": 50.0, "thread": "M16"},
        "uom": "NOS"
    }

    scores = calculate_match_scores(semantic_similarity=1.0, mat_a_data=mat_a, mat_b_data=mat_b)

    assert scores["semantic_score"] == 1.0
    assert scores["material_score"] == 1.0
    assert scores["dimension_score"] == 1.0
    assert scores["category_score"] == 1.0
    assert scores["specification_score"] == 1.0
    assert scores["uom_score"] == 1.0
    assert scores["final_confidence"] >= 99.0

def test_custom_weights_effect():
    mat_a = {"material": "Stainless Steel", "dimensions": {"length_mm": 50.0}, "category": "Fasteners"}
    mat_b = {"material": "Carbon Steel", "dimensions": {"length_mm": 50.0}, "category": "Fasteners"}

    # Custom weights emphasizing material match 80%
    custom_w = {
        "semantic_similarity": 0.10,
        "material_match": 0.80,
        "dimension_match": 0.05,
        "category_match": 0.05,
        "specification_match": 0.0,
        "uom_match": 0.0
    }

    scores = calculate_match_scores(0.9, mat_a, mat_b, custom_weights=custom_w)
    # Material mismatch should heavily pull down final confidence
    assert scores["final_confidence"] < 60.0
