from sqlalchemy.orm import Session
from app.database.db import engine, init_db, SessionLocal
from app.database.models import User, Category
from app.config import get_taxonomy_config

def seed_database():
    """
    Initializes tables, inserts standard users, seeds the taxonomy tree from taxonomy.yaml,
    and loads the demo dataset.
    """
    init_db()
    db = SessionLocal()
    try:
        # 1. Seed standard demo users
        users = [
            ("Admin Officer", "Admin"),
            ("Senior Procurement Officer", "Procurement Officer"),
            ("Inventory Viewer", "Viewer"),
        ]
        for uname, role in users:
            existing = db.query(User).filter(User.username == uname).first()
            if not existing:
                db.add(User(username=uname, role=role))
        db.commit()

        # 2. Seed Category / Subcategory taxonomy tree
        tax_config = get_taxonomy_config()
        for cat in tax_config.get("categories", []):
            c_name = cat.get("name")
            c_abbrev = cat.get("abbrev")
            parent_cat = db.query(Category).filter(Category.name == c_name, Category.parent_id == None).first()
            if not parent_cat:
                parent_cat = Category(name=c_name, abbrev=c_abbrev)
                db.add(parent_cat)
                db.flush()

            for subcat in cat.get("subcategories", []):
                s_name = subcat.get("name")
                existing_sub = db.query(Category).filter(
                    Category.name == s_name, Category.parent_id == parent_cat.id
                ).first()
                if not existing_sub:
                    db.add(Category(name=s_name, parent_id=parent_cat.id, abbrev=c_abbrev))

        db.commit()

        # Demo dataset must NEVER be seeded automatically.
        # Data is only loaded when an officer clicks 'Load Demo Dataset' or uploads a spreadsheet.
        print("Schema, users, and taxonomy seeded successfully (empty operational database).")

    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
