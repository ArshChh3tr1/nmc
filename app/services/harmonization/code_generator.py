from sqlalchemy.orm import Session
from app.database.models import HarmonizedMaterial, Category

def generate_common_material_code(db: Session, category_abbrev: str) -> str:
    """
    Generates the next sequential Common Material Code recommendation: NMC-<CAT>-<####>
    Does NOT write to database. Recommendation only.
    """
    abbrev = (category_abbrev or "GEN").upper().strip()
    prefix = f"NMC-{abbrev}-"

    # Query existing codes starting with this prefix
    existing = db.query(HarmonizedMaterial.common_code).filter(
        HarmonizedMaterial.common_code.like(f"{prefix}%")
    ).all()

    max_seq = 0
    for row in existing:
        code_str = row[0]
        try:
            seq_part = code_str.split("-")[-1]
            seq_num = int(seq_part)
            if seq_num > max_seq:
                max_seq = seq_num
        except (ValueError, IndexError):
            pass

    next_seq = max_seq + 1
    return f"{prefix}{next_seq:04d}"
