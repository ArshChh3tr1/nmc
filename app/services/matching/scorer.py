import json
from typing import Dict, Any, Tuple
from rapidfuzz import fuzz
from app.config import get_weights_config
from app.services.normalization.attribute_extractor import extract_attributes

KNOWN_CANONICAL_MATERIALS = {
    "stainless steel", "stainless steel 304", "stainless steel 316",
    "carbon steel", "mild steel", "brass", "bronze", "copper",
    "aluminium", "cast iron", "ptfe", "viton", "nitrile rubber"
}

def compute_material_score(mat_a: str, mat_b: str) -> float:
    if not mat_a or not mat_b or mat_a == "Generic / Unspecified" or mat_b == "Generic / Unspecified":
        return 0.5
    ma = mat_a.strip().lower()
    mb = mat_b.strip().lower()
    if ma == mb:
        return 1.0
    # If both are known distinct canonical materials, score is strictly 0.0
    if ma in KNOWN_CANONICAL_MATERIALS and mb in KNOWN_CANONICAL_MATERIALS:
        return 0.0
    # Rapidfuzz partial ratio for non-canonical fallback strings
    ratio = fuzz.ratio(ma, mb) / 100.0
    return round(ratio, 3)

def compute_dimension_score(dims_a: Dict[str, Any], dims_b: Dict[str, Any]) -> Tuple[float, bool, str]:
    """
    Compares dimensions dictionary.
    Returns: (dimension_score: float in [0, 1], has_conflict: bool, conflict_details: str)
    Any hard conflict (e.g. 50mm vs 80mm length) sharply reduces score to 0.0 and sets has_conflict=True.
    """
    if not dims_a and not dims_b:
        return 0.8, False, ""  # Neither specified dimensions; plausible match

    if not dims_a or not dims_b:
        return 0.5, False, "One item lacks dimension data"

    conflicts = []
    comparisons = 0
    matches = 0

    # 1. Thread check
    if "thread" in dims_a and "thread" in dims_b:
        comparisons += 1
        if dims_a["thread"].upper() == dims_b["thread"].upper():
            matches += 1
        else:
            conflicts.append(f"Thread differs: {dims_a['thread']} vs {dims_b['thread']}")

    # 2. Diameter check
    if "diameter_mm" in dims_a and "diameter_mm" in dims_b:
        comparisons += 1
        da = float(dims_a["diameter_mm"])
        db = float(dims_b["diameter_mm"])
        if abs(da - db) < 0.1:  # tight tolerance
            matches += 1
        else:
            conflicts.append(f"Diameter differs: {da}mm vs {db}mm")

    # 3. Length check
    if "length_mm" in dims_a and "length_mm" in dims_b:
        comparisons += 1
        la = float(dims_a["length_mm"])
        lb = float(dims_b["length_mm"])
        if abs(la - lb) < 0.5:
            matches += 1
        else:
            conflicts.append(f"Length differs: {la}mm vs {lb}mm")

    # 4. Bearing code
    if "bearing_code" in dims_a and "bearing_code" in dims_b:
        comparisons += 1
        ba = dims_a["bearing_code"].upper()
        bb = dims_b["bearing_code"].upper()
        if ba == bb:
            matches += 1
        else:
            conflicts.append(f"Bearing code differs: {ba} vs {bb}")

    # 5. Nominal Bore & Schedule & Pressure Class
    if "nominal_bore" in dims_a and "nominal_bore" in dims_b:
        comparisons += 1
        if abs(float(dims_a["nominal_bore"]) - float(dims_b["nominal_bore"])) < 0.1:
            matches += 1
        else:
            conflicts.append(f"Nominal bore differs: {dims_a['nominal_bore']} vs {dims_b['nominal_bore']}")

    if "schedule" in dims_a and "schedule" in dims_b:
        comparisons += 1
        if str(dims_a["schedule"]).upper() == str(dims_b["schedule"]).upper():
            matches += 1
        else:
            conflicts.append(f"Schedule differs: {dims_a['schedule']} vs {dims_b['schedule']}")

    if "pressure_class" in dims_a and "pressure_class" in dims_b:
        comparisons += 1
        if dims_a["pressure_class"] == dims_b["pressure_class"]:
            matches += 1
        else:
            conflicts.append(f"Pressure class differs: #{dims_a['pressure_class']} vs #{dims_b['pressure_class']}")

    if conflicts:
        conflict_msg = "; ".join(conflicts)
        return 0.0, True, conflict_msg

    if comparisons == 0:
        return 0.7, False, ""

    score = matches / comparisons
    return round(score, 3), False, ""

def compute_category_score(cat_a: str, subcat_a: str, cat_b: str, subcat_b: str) -> float:
    if not cat_a or not cat_b:
        return 0.0
    if cat_a.lower() == cat_b.lower():
        if subcat_a and subcat_b and subcat_a.lower() == subcat_b.lower():
            return 1.0
        return 0.5
    return 0.0

def compute_specification_score(spec_a: str, spec_b: str) -> float:
    if not spec_a or not spec_b or spec_a == "Standard" or spec_b == "Standard":
        return 0.8  # both generic standard
    sa = spec_a.strip().lower()
    sb = spec_b.strip().lower()
    if sa == sb:
        return 1.0
    ratio = fuzz.token_sort_ratio(sa, sb) / 100.0
    return round(ratio, 3)

def compute_uom_score(uom_a: str, uom_b: str) -> float:
    if not uom_a or not uom_b:
        return 1.0
    return 1.0 if uom_a.strip().upper() == uom_b.strip().upper() else 0.0

def calculate_match_scores(
    semantic_similarity: float,
    mat_a_data: Dict[str, Any],
    mat_b_data: Dict[str, Any],
    custom_weights: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Computes all component scores and weighted final confidence.
    """
    cfg = get_weights_config()
    weights = custom_weights or cfg.get("weights", {})

    w_semantic = float(weights.get("semantic_similarity", 0.40))
    w_material = float(weights.get("material_match", 0.20))
    w_dim = float(weights.get("dimension_match", 0.15))
    w_cat = float(weights.get("category_match", 0.10))
    w_spec = float(weights.get("specification_match", 0.10))
    w_uom = float(weights.get("uom_match", 0.05))

    mat_score = compute_material_score(mat_a_data.get("material", ""), mat_b_data.get("material", ""))

    dims_a = mat_a_data.get("dimensions", {})
    if isinstance(dims_a, str):
        try:
            dims_a = json.loads(dims_a)
        except Exception:
            dims_a = {}
    if not dims_a or not isinstance(dims_a, dict):
        raw_t = mat_a_data.get("dimensions") or mat_a_data.get("raw_description") or ""
        if isinstance(raw_t, str) and raw_t and raw_t != "{}":
            dims_a = extract_attributes(raw_t).get("dimensions", {})

    dims_b = mat_b_data.get("dimensions", {})
    if isinstance(dims_b, str):
        try:
            dims_b = json.loads(dims_b)
        except Exception:
            dims_b = {}
    if not dims_b or not isinstance(dims_b, dict):
        raw_t = mat_b_data.get("dimensions") or mat_b_data.get("raw_description") or ""
        if isinstance(raw_t, str) and raw_t and raw_t != "{}":
            dims_b = extract_attributes(raw_t).get("dimensions", {})

    dim_score, has_dim_conflict, conflict_details = compute_dimension_score(dims_a, dims_b)

    cat_score = compute_category_score(
        mat_a_data.get("category", ""), mat_a_data.get("subcategory", ""),
        mat_b_data.get("category", ""), mat_b_data.get("subcategory", "")
    )

    spec_score = compute_specification_score(
        mat_a_data.get("specification", ""), mat_b_data.get("specification", "")
    )

    uom_score = compute_uom_score(mat_a_data.get("uom", ""), mat_b_data.get("uom", ""))

    # Clamp semantic score
    sem_score = max(0.0, min(1.0, float(semantic_similarity)))

    final_score = (
        sem_score * w_semantic +
        mat_score * w_material +
        dim_score * w_dim +
        cat_score * w_cat +
        spec_score * w_spec +
        uom_score * w_uom
    )

    final_confidence = round(final_score * 100.0, 1)

    return {
        "semantic_score": round(sem_score, 4),
        "material_score": round(mat_score, 3),
        "dimension_score": round(dim_score, 3),
        "category_score": round(cat_score, 3),
        "specification_score": round(spec_score, 3),
        "uom_score": round(uom_score, 3),
        "final_confidence": final_confidence,
        "has_dimension_conflict": has_dim_conflict,
        "conflict_details": conflict_details,
        "weights_used": weights
    }
