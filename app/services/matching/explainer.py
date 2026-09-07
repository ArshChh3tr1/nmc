import json
from typing import Dict, Any

def generate_explanation(
    mat_a: Dict[str, Any],
    mat_b: Dict[str, Any],
    score_data: Dict[str, Any],
    match_type: str
) -> str:
    """
    Generates a structured human-readable explainable AI breakdown.
    Uses ✓ for matching components and ✗ with plain-language notes for failures/conflicts.
    """
    sem_pct = score_data.get("semantic_score", 0.0) * 100.0
    conf_pct = score_data.get("final_confidence", 0.0)

    dims_a = mat_a.get("dimensions", {})
    if isinstance(dims_a, str):
        try:
            dims_a = json.loads(dims_a)
        except Exception:
            dims_a = {}

    dims_b = mat_b.get("dimensions", {})
    if isinstance(dims_b, str):
        try:
            dims_b = json.loads(dims_b)
        except Exception:
            dims_b = {}

    lines = ["AI MATCH ANALYSIS"]
    lines.append(f"Semantic similarity: {sem_pct:.1f}%")

    # Material
    mat_score = score_data.get("material_score", 0.0)
    ma = mat_a.get("material", "Unspecified")
    mb = mat_b.get("material", "Unspecified")
    if mat_score >= 0.95:
        lines.append(f"Material: ✓ Same ({ma})")
    elif mat_score >= 0.6:
        lines.append(f"Material: ~ Compatible ({ma} vs {mb})")
    else:
        lines.append(f"Material: ✗ Differs ({ma} vs {mb})")

    # Category & Subcategory
    cat_score = score_data.get("category_score", 0.0)
    ca = mat_a.get("category", "")
    cb = mat_b.get("category", "")
    if cat_score >= 0.99:
        lines.append(f"Category: ✓ Same ({ca})")
    elif cat_score >= 0.5:
        lines.append(f"Category: ~ Same family ({ca})")
    else:
        lines.append(f"Category: ✗ Differs ({ca} vs {cb})")

    # Type
    ta = mat_a.get("material_type", "") or mat_a.get("type", "")
    tb = mat_b.get("material_type", "") or mat_b.get("type", "")
    if ta and tb and ta.lower() == tb.lower():
        lines.append(f"Type: ✓ Same ({ta})")
    elif ta and tb:
        lines.append(f"Type: ✗ Differs ({ta} vs {tb})")
    else:
        lines.append("Type: ~ Not explicitly specified")

    # Dimensions: Thread / Diameter
    if "diameter_mm" in dims_a and "diameter_mm" in dims_b:
        da = dims_a["diameter_mm"]
        db = dims_b["diameter_mm"]
        if abs(float(da) - float(db)) < 0.1:
            lines.append(f"Diameter: ✓ Same ({da}mm)")
        else:
            lines.append(f"Diameter: ✗ Differs ({da}mm vs {db}mm — Specification Conflict)")
    elif "thread" in dims_a and "thread" in dims_b:
        ta_th = dims_a["thread"]
        tb_th = dims_b["thread"]
        if ta_th.upper() == tb_th.upper():
            lines.append(f"Thread: ✓ Same ({ta_th})")
        else:
            lines.append(f"Thread: ✗ Differs ({ta_th} vs {tb_th} — Specification Conflict)")

    # Dimensions: Length
    if "length_mm" in dims_a and "length_mm" in dims_b:
        la = dims_a["length_mm"]
        lb = dims_b["length_mm"]
        if abs(float(la) - float(lb)) < 0.5:
            lines.append(f"Length: ✓ Same ({la}mm)")
        else:
            lines.append(f"Length: ✗ Differs ({la}mm vs {lb}mm — Specification Conflict)")

    # Dimensions: Bearing Code
    if "bearing_code" in dims_a and "bearing_code" in dims_b:
        ba = dims_a["bearing_code"]
        bb = dims_b["bearing_code"]
        if ba == bb:
            lines.append(f"Bearing Code: ✓ Same ({ba})")
        else:
            lines.append(f"Bearing Code: ✗ Differs ({ba} vs {bb} — Specification Conflict)")

    # Specification / Standard
    spec_score = score_data.get("specification_score", 0.0)
    sa = mat_a.get("specification", "Standard")
    sb = mat_b.get("specification", "Standard")
    if spec_score >= 0.95:
        lines.append(f"Specification: ✓ Same ({sa})")
    elif spec_score >= 0.7:
        lines.append(f"Specification: ~ Compatible ({sa} vs {sb})")
    else:
        lines.append(f"Specification: ✗ Differs ({sa} vs {sb})")

    # UOM
    uom_score = score_data.get("uom_score", 0.0)
    ua = mat_a.get("uom", "NOS")
    ub = mat_b.get("uom", "NOS")
    if uom_score >= 0.99:
        lines.append(f"UOM: ✓ Same ({ua})")
    else:
        lines.append(f"UOM: ✗ Unit mismatch ({ua} vs {ub})")

    lines.append(f"FINAL CONFIDENCE: {conf_pct:.1f}%")

    # Recommendation
    if match_type == "EXACT_DUPLICATE":
        rec = "High-confidence duplicate"
    elif match_type == "NEAR_DUPLICATE":
        rec = "High-confidence near-duplicate (text variation only)"
    elif match_type == "FUNCTIONALLY_EQUIVALENT":
        rec = "Functionally equivalent — Officer review recommended"
    elif match_type == "SIMILAR_NOT_EQUIVALENT":
        if score_data.get("has_dimension_conflict", False):
            rec = "Specification Conflict — Do NOT merge without engineering review"
        else:
            rec = "Similar items, different specifications"
    else:
        rec = "No match"

    lines.append(f"RECOMMENDATION: {rec}")
    return "\n".join(lines)
