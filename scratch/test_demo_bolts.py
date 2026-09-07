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
b1 = db.query(Material).filter(Material.legacy_code == 'IO-FST-48392').first()
b2 = db.query(Material).filter(Material.legacy_code == 'BP-FST-99213').first()
b3 = db.query(Material).filter(Material.legacy_code == 'HP-FST-18372').first()
bolts = [b for b in [b1, b2, b3] if b]

def to_dict(m):
    return {
        'id': m.id, 'cpse': m.cpse, 'legacy_code': m.legacy_code,
        'material': m.material_type,
        'category': m.category.name if m.category else '',
        'subcategory': m.category.name if m.category else '',
        'material_type': m.material_type,
        'dimensions': m.dimensions_json or '{}',
        'specification': m.specification or 'Standard',
        'uom': m.uom or 'NOS',
        'raw_description': m.raw_description
    }

for i in range(len(bolts)):
    for j in range(i+1, len(bolts)):
        ba = bolts[i]
        bb = bolts[j]
        v1 = compute_embedding(ba.normalized_description)
        v2 = compute_embedding(bb.normalized_description)
        sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        da = to_dict(ba)
        db_d = to_dict(bb)
        scores = calculate_match_scores(sim, da, db_d)
        mtype, desc = classify_match(scores)
        print(f"{ba.cpse}:{ba.legacy_code} vs {bb.cpse}:{bb.legacy_code}: conf={scores['final_confidence']}%, sim={scores['semantic_score']}, dim={scores['dimension_score']}, mat={scores['material_score']}, spec={scores['specification_score']}, cat={scores['category_score']}, uom={scores['uom_score']} => {mtype} | {desc}")
db.close()
