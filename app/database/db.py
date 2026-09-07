from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from app.config import DB_URL
from app.database.models import Base

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE match_groups ADD COLUMN auto_approval_reason VARCHAR(255)"))
            conn.commit()
        except Exception:
            pass

def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def clear_all_data(db):
    """
    Safely wipes all operational tables (materials, inventory, matches, groups, mappings,
    harmonized materials, warehouses, suppliers, audit logs) to reset the app to an empty state.
    Preserves users and core taxonomy schema.
    """
    from app.database.models import (
        MatchGroupMember, MatchGroup, MatchResult, MaterialMapping,
        HarmonizedMaterial, Inventory, Material, Warehouse, Supplier, AuditLog
    )
    db.query(MatchGroupMember).delete()
    db.query(MatchGroup).delete()
    db.query(MatchResult).delete()
    db.query(MaterialMapping).delete()
    db.query(HarmonizedMaterial).delete()
    db.query(Inventory).delete()
    db.query(Material).delete()
    db.query(Warehouse).delete()
    db.query(Supplier).delete()
    db.query(AuditLog).delete()
    db.commit()
    return True, "All materials, inventory, match groups, and operational records cleared successfully."

