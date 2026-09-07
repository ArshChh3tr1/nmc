from typing import Dict, Any, Tuple
from app.config import get_weights_config

def classify_match(score_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Categorizes the match into one of:
    - EXACT_DUPLICATE
    - NEAR_DUPLICATE
    - FUNCTIONALLY_EQUIVALENT
    - SIMILAR_NOT_EQUIVALENT
    - NO_MATCH

    Enforces strict hard-conflict rule:
    If has_dimension_conflict is True, it MUST be classified as SIMILAR_NOT_EQUIVALENT
    with a 'Specification Conflict' flag, regardless of how high the semantic score is.
    """
    conf = score_data.get("final_confidence", 0.0)
    has_dim_conflict = score_data.get("has_dimension_conflict", False)
    conflict_details = score_data.get("conflict_details", "")

    mat_score = score_data.get("material_score", 0.0)
    dim_score = score_data.get("dimension_score", 0.0)
    cat_score = score_data.get("category_score", 0.0)
    spec_score = score_data.get("specification_score", 0.0)
    uom_score = score_data.get("uom_score", 0.0)

    # Hard conflict override: any dimension mismatch prevents duplicate classification
    if has_dim_conflict:
        desc = f"Specification Conflict: {conflict_details}. Not functionally interchangeable."
        return "SIMILAR_NOT_EQUIVALENT", desc

    cfg = get_weights_config().get("thresholds", {})
    exact_min = cfg.get("exact_duplicate_min", 95.0)
    high_min = cfg.get("high_confidence_min", 90.0)
    med_min = cfg.get("medium_confidence_min", 80.0)
    low_min = cfg.get("low_confidence_min", 60.0)

    # EXACT_DUPLICATE: confidence >= 95 and all attribute components match (no conflict)
    if conf >= exact_min and mat_score >= 0.95 and cat_score >= 0.95 and uom_score >= 0.95 and spec_score >= 0.8 and dim_score >= 0.7:
        return "EXACT_DUPLICATE", "Identical material, dimensions, standard, and UOM."

    # NEAR_DUPLICATE: confidence >= 90, formatting/abbreviation differences only
    if conf >= high_min and mat_score >= 0.8 and cat_score >= 0.8 and dim_score >= 0.6:
        return "NEAR_DUPLICATE", "Equivalent material with minor phrasing or abbreviation variation."

    # Fallback near-duplicate: if confidence >= exact_min (95.0) and NO conflict exists,
    # never label as functionally equivalent when material and category match
    if conf >= exact_min and mat_score >= 0.8 and cat_score >= 0.8:
        return "NEAR_DUPLICATE", "High-confidence duplicate material with minor specification or formatting variation."

    # FUNCTIONALLY_EQUIVALENT: confidence 80-89.9, same category/function, non-critical variant
    if conf >= med_min:
        return "FUNCTIONALLY_EQUIVALENT", "Functionally equivalent; minor specification or supplier variation requires officer verification."

    # SIMILAR_NOT_EQUIVALENT: confidence 60-79
    if conf >= low_min:
        return "SIMILAR_NOT_EQUIVALENT", "Similar family or usage, but key specifications or dimensions differ."

    # NO_MATCH
    return "NO_MATCH", "Different materials with insufficient similarity."
