import io
import pandas as pd
from typing import Tuple, Dict, Any, Union
from sqlalchemy.orm import Session
from app.utils.validators import validate_dataframe
from app.database.models import Material, Inventory, Warehouse, Supplier, Category
from app.services.normalization.normalizer import normalize_text
from app.services.normalization.attribute_extractor import extract_attributes
from app.services.classification.classifier import classify_material
from app.services.audit.audit_logger import log_action

def ingest_material_file(
    db: Session,
    file_bytes_or_path: Union[bytes, str, Any],
    file_name: str,
    actor_name: str = "Procurement Officer",
    check_all_expected: bool = True
) -> Tuple[bool, Dict[str, Any]]:
    """
    Ingests CSV or Excel file, validates schema, normalizes text, extracts attributes,
    classifies categories, and stores records without crashing.
    """
    report: Dict[str, Any] = {}
    try:
        if hasattr(file_bytes_or_path, "getvalue"):
            content_bytes = file_bytes_or_path.getvalue()
            bio = io.BytesIO(content_bytes)
            if file_name.lower().endswith(".csv"):
                df = pd.read_csv(bio)
            else:
                df = pd.read_excel(bio, sheet_name=0)
        elif isinstance(file_bytes_or_path, (bytes, bytearray)):
            bio = io.BytesIO(bytes(file_bytes_or_path))
            if file_name.lower().endswith(".csv"):
                df = pd.read_csv(bio)
            else:
                df = pd.read_excel(bio, sheet_name=0)
        else:
            if str(file_bytes_or_path).lower().endswith(".csv"):
                df = pd.read_csv(file_bytes_or_path)
            else:
                df = pd.read_excel(file_bytes_or_path, sheet_name=0)

        cleaned_df, report = validate_dataframe(df, check_all_expected=check_all_expected)
        if cleaned_df.empty:
            return False, report

        inserted_count = 0
        existing_count = 0

        for _, row in cleaned_df.iterrows():
            cpse = row["CPSE"]
            legacy_code = row["Legacy Material Code"]
            raw_desc = row["Raw Material Description"]

            # Normalize text
            norm_desc = normalize_text(raw_desc)

            # Extract attributes
            extracted = extract_attributes(raw_desc, norm_desc, row.get("UOM"))
            mat_type = str(row.get("Material", "") or "").strip() or extracted["material"]
            item_type = extracted["type"]
            spec = str(row.get("Specification", "") or "").strip() or extracted["specification"]
            dims_json = str(row.get("Dimensions", "") or "").strip() or extracted["dimensions_json"]
            uom = str(row.get("UOM", "") or "").strip() or extracted["uom"]
            unit_price = float(row.get("Unit Price", 0.0) or 0.0)

            # Classify category (use user-specified if present, else classifier)
            user_cat = str(row.get("Category", "") or "").strip()
            user_subcat = str(row.get("Subcategory", "") or "").strip()
            cat_name, subcat_name, cat_abbrev = classify_material(norm_desc, item_type)
            if user_cat:
                cat_name = user_cat

            # Find or create Category in DB
            category_obj = db.query(Category).filter(Category.name == cat_name).first()
            if not category_obj:
                category_obj = Category(name=cat_name, abbrev=cat_abbrev)
                db.add(category_obj)
                db.flush()

            subcat_final = user_subcat or subcat_name
            if subcat_final and category_obj:
                sub_obj = db.query(Category).filter(
                    Category.name == subcat_final,
                    Category.parent_id == category_obj.id
                ).first()
                if not sub_obj:
                    sub_obj = Category(name=subcat_final, parent_id=category_obj.id, abbrev=cat_abbrev)
                    db.add(sub_obj)
                    db.flush()

            # Find or create Warehouse
            wh_name = row.get("Warehouse") or f"{cpse}-Central-Depot"
            wh_obj = db.query(Warehouse).filter(Warehouse.name == wh_name).first()
            if not wh_obj:
                wh_obj = Warehouse(name=wh_name, cpse=cpse, location="Central Industrial Store")
                db.add(wh_obj)
                db.flush()

            # Find or create Supplier
            sup_name = row.get("Supplier") or "Standard CPSE Vendor"
            sup_obj = db.query(Supplier).filter(Supplier.name == sup_name).first()
            if not sup_obj:
                sup_obj = Supplier(name=sup_name, contact_info="procurement@cpse-vendor.in")
                db.add(sup_obj)
                db.flush()

            # Check if material already exists (idempotent reload)
            material = db.query(Material).filter(
                Material.cpse == cpse,
                Material.legacy_code == legacy_code
            ).first()

            if not material:
                material = Material(
                    cpse=cpse,
                    legacy_code=legacy_code,
                    raw_description=raw_desc,
                    normalized_description=norm_desc,
                    category_id=category_obj.id,
                    material_type=mat_type,
                    specification=spec,
                    dimensions_json=dims_json,
                    uom=uom,
                    unit_price=unit_price,
                    status="raw"
                )
                db.add(material)
                db.flush()
                inserted_count += 1

                # Add Inventory row
                inv = Inventory(
                    material_id=material.id,
                    warehouse_id=wh_obj.id,
                    supplier_id=sup_obj.id,
                    available_qty=float(row.get("Available Quantity", 0.0)),
                    reserved_qty=float(row.get("Reserved Quantity", 0.0)),
                    on_order_qty=float(row.get("On Order Quantity", 0.0)),
                    reorder_level=float(row.get("Reorder Level", 0.0))
                )
                db.add(inv)
            else:
                existing_count += 1

        db.commit()

        report["new_materials"] = inserted_count
        report["existing_materials"] = existing_count

        log_action(
            db=db,
            actor=actor_name,
            action="Data Ingestion",
            entity_type="BatchUpload",
            entity_id=file_name,
            details=f"Loaded {report['valid_records']} valid records from {file_name}. {inserted_count} new materials created, {existing_count} existing."
        )

        return True, report

    except Exception as e:
        report["errors"] = [f"Ingestion failed due to unexpected error: {str(e)}"]
        return False, report
