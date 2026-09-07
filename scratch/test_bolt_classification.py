import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.db import SessionLocal
from app.database.models import Material
from app.services.matching.scorer import calculate_match_scores
from app.services.matching.classifier_match import classify_match
from app.services.embeddings.embedder import compute_embedding
import numpy as np

db = SessionLocal()
bolts = db.query(Material).filter(Material.raw_description.ilike('%M16%50%')).all()
print(f'Total M16x50 bolts in db: {len(bolts)}')
for b in bolts:
    print(f"ID={b.id}, CPSE={b.cpse}, Code={b.legacy_code}, Raw='{b.raw_description}', Spec='{b.specification}', Mat='{b.material_type}', Dims='{b.dimensions_json}'")

print("\n--- Pairwise Comparisons ---")
def to_dict(m):
    return {
        "id": m.id,
        "cpse": m.cpse,
        "legacy_code": m.legacy_code,
        "material": m.material_type,
        "category": m.category.name if m.category else "",
        "subcategory": m.category.name if m.category else "",
        "material_type": m.material_type,
        "dimensions": m.dimensions_json or "{}",
        "specification": m.specification or "Standard",
        "uom": m.uom or "NOS",
        "raw_description": m.raw_description
    }

for i in range(len(bolts)):
    for j in range(i+1, len(bolts)):
        b1 = bolts[i]
        b2 = bolts[j]
        v1 = compute_embedding(b1.normalized_description)
        v2 = compute_embedding(b2.normalized_description)
        sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        d1 = to_dict(b1)
        d2 = to_dict(b2)
        scores = calculate_match_scores(sim, d1, d2)
        m_type, desc = classify_match(scores)
        print(f"{b1.cpse}:{b1.legacy_code} vs {b2.cpse}:{b2.legacy_code} -> conf={scores['final_confidence']}%, sim={scores['semantic_score']}, dim={scores['dimension_score']}, mat={scores['material_score']}, spec={scores['specification_score']}, cat={scores['category_score']}, uom={scores['uom_score']} => {m_type}")

db.close()
