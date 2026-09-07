import numpy as np
import json
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.database.models import Material, Category, MatchResult
from app.services.embeddings.embedder import get_embedder
from app.services.embeddings.vector_index import FaissVectorIndex
from app.services.matching.scorer import calculate_match_scores
from app.services.matching.classifier_match import classify_match
from app.services.matching.explainer import generate_explanation
from app.config import TOP_K_CANDIDATES

def build_material_embedding_text(material: Material) -> str:
    parts = [material.normalized_description or material.raw_description]
    if material.material_type:
        parts.append(f"Type: {material.material_type}")
    if material.specification and material.specification != "Standard":
        parts.append(f"Spec: {material.specification}")
    if material.dimensions_json:
        try:
            dims = json.loads(material.dimensions_json)
            for k, v in dims.items():
                parts.append(f"{k}: {v}")
        except Exception:
            pass
    if material.uom:
        parts.append(f"UOM: {material.uom}")
    return " | ".join(parts)

def run_candidate_search_and_matching(
    db: Session,
    top_k: int = TOP_K_CANDIDATES,
    progress_callback = None
) -> List[MatchResult]:
    """
    1. Indexes all processed materials using FAISS IndexFlatIP.
    2. Searches top-K nearest neighbors within the same category family.
    3. Performs attribute comparison and weighted scoring.
    4. Enforces hard dimension conflict rules.
    5. Stores candidate match_results in the database.
    """
    materials = db.query(Material).all()
    if not materials or len(materials) < 2:
        return []

    if progress_callback:
        progress_callback("Generating dense semantic embeddings...", 0.2)

    embedder = get_embedder()
    texts = [build_material_embedding_text(m) for m in materials]
    vectors = embedder.embed_texts(texts)

    # Save embedding vectors back to DB for fast reload
    for m, vec in zip(materials, vectors):
        m.embedding_vector = vec.tobytes()
        if m.status == "raw":
            m.status = "processed"
    db.commit()

    if progress_callback:
        progress_callback("Building FAISS vector index...", 0.4)

    # Group by category_id to ensure candidates are compared within same or compatible category
    cat_to_indices: Dict[int, List[int]] = {}
    for idx, m in enumerate(materials):
        c_id = m.category_id or 0
        cat_to_indices.setdefault(c_id, []).append(idx)

    match_results: List[MatchResult] = []
    seen_pairs = set()

    # Clear previous pending matches to avoid stale duplicates
    db.query(MatchResult).filter(MatchResult.status == "pending").delete()
    db.commit()

    if progress_callback:
        progress_callback("Running candidate retrieval & specification-aware scoring...", 0.7)

    # Build category-aware indices
    for cat_id, indices in cat_to_indices.items():
        if len(indices) < 2:
            continue

        cat_materials = [materials[i] for i in indices]
        cat_vectors = vectors[indices]

        sub_index = FaissVectorIndex(dimension=384)
        sub_index.add_materials([m.id for m in cat_materials], cat_vectors)

        for i, m_a in enumerate(cat_materials):
            vec_a = cat_vectors[i]
            # Query top_k neighbors
            candidates = sub_index.search(vec_a, top_k=top_k)

            for mat_b_id, sem_score in candidates:
                if mat_b_id == m_a.id:
                    continue

                pair_key = tuple(sorted([m_a.id, mat_b_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                m_b = next((x for x in cat_materials if x.id == mat_b_id), None)
                if not m_b:
                    continue

                # Don't match materials from the exact same CPSE with identical legacy code
                if m_a.cpse == m_b.cpse and m_a.legacy_code == m_b.legacy_code:
                    continue

                # Convert to dicts for scorer
                mat_a_dict = {
                    "id": m_a.id,
                    "cpse": m_a.cpse,
                    "legacy_code": m_a.legacy_code,
                    "material": m_a.material_type,
                    "category": m_a.category.name if m_a.category else "",
                    "subcategory": m_a.category.name if m_a.category else "",
                    "material_type": m_a.material_type,
                    "dimensions": m_a.dimensions_json or "{}",
                    "specification": m_a.specification or "Standard",
                    "uom": m_a.uom or "NOS",
                    "raw_description": m_a.raw_description
                }

                mat_b_dict = {
                    "id": m_b.id,
                    "cpse": m_b.cpse,
                    "legacy_code": m_b.legacy_code,
                    "material": m_b.material_type,
                    "category": m_b.category.name if m_b.category else "",
                    "subcategory": m_b.category.name if m_b.category else "",
                    "material_type": m_b.material_type,
                    "dimensions": m_b.dimensions_json or "{}",
                    "specification": m_b.specification or "Standard",
                    "uom": m_b.uom or "NOS",
                    "raw_description": m_b.raw_description
                }

                scores = calculate_match_scores(sem_score, mat_a_dict, mat_b_dict)
                match_type, summary_desc = classify_match(scores)
                explanation = generate_explanation(mat_a_dict, mat_b_dict, scores, match_type)

                # Only persist plausible matches (confidence >= 50 or semantic score >= 0.5)
                if scores["final_confidence"] >= 50.0 or scores["semantic_score"] >= 0.55:
                    match_record = MatchResult(
                        material_a_id=m_a.id,
                        material_b_id=m_b.id,
                        semantic_score=scores["semantic_score"],
                        material_score=scores["material_score"],
                        dimension_score=scores["dimension_score"],
                        category_score=scores["category_score"],
                        specification_score=scores["specification_score"],
                        uom_score=scores["uom_score"],
                        final_confidence=scores["final_confidence"],
                        match_type=match_type,
                        explanation_text=explanation,
                        status="pending"
                    )
                    db.add(match_record)
                    match_results.append(match_record)

    db.commit()

    if progress_callback:
        progress_callback("Clustering matches into N-way material groups & auto-approving...", 0.9)

    from app.services.matching.grouping import build_and_save_match_groups
    build_and_save_match_groups(db)

    if progress_callback:
        progress_callback("AI Harmonization candidate analysis complete!", 1.0)

    return match_results
