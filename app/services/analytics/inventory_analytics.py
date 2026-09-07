from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import (
    Material, HarmonizedMaterial, MaterialMapping, Inventory, MatchResult, Warehouse
)

def get_harmonized_inventory_aggregation(db: Session) -> List[Dict[str, Any]]:
    """
    Aggregates inventory per Harmonized Material across all mapped CPSEs and warehouses.
    Computes total available, total reserved, on order, and distinct CPSE counts.
    """
    harmonized = db.query(HarmonizedMaterial).all()
    records = []

    for hm in harmonized:
        # Fetch all mapped materials
        mappings = hm.mappings
        mat_ids = [m.material_id for m in mappings]

        if not mat_ids:
            continue

        inventories = db.query(Inventory).filter(Inventory.material_id.in_(mat_ids)).all()

        total_avail = sum(inv.available_qty for inv in inventories)
        total_reserved = sum(inv.reserved_qty for inv in inventories)
        total_on_order = sum(inv.on_order_qty for inv in inventories)
        total_reorder_lvl = sum(inv.reorder_level for inv in inventories)

        # CPSE breakdown
        cpse_breakdown: Dict[str, Dict[str, float]] = {}
        for inv in inventories:
            cpse_name = inv.material.cpse
            if cpse_name not in cpse_breakdown:
                cpse_breakdown[cpse_name] = {"available": 0.0, "unit_price": inv.material.unit_price, "warehouses": []}
            cpse_breakdown[cpse_name]["available"] += inv.available_qty
            wh_name = inv.warehouse.name if inv.warehouse else "Central"
            if wh_name not in cpse_breakdown[cpse_name]["warehouses"]:
                cpse_breakdown[cpse_name]["warehouses"].append(wh_name)

        # Average unit price
        prices = [inv.material.unit_price for inv in inventories if inv.material.unit_price > 0]
        avg_price = (sum(prices) / len(prices)) if prices else 0.0
        total_value = total_avail * avg_price

        # Duplicate stock exists if stocked by 2+ CPSEs
        is_duplicate_stock = len(cpse_breakdown) >= 2 and total_avail > 0

        records.append({
            "harmonized_id": hm.id,
            "common_code": hm.common_code,
            "standard_description": hm.standard_description,
            "category": hm.category.name if hm.category else "General",
            "material_type": hm.material_type,
            "specification": hm.specification,
            "uom": hm.uom,
            "total_available": total_avail,
            "total_reserved": total_reserved,
            "total_on_order": total_on_order,
            "total_reorder_level": total_reorder_lvl,
            "avg_unit_price": avg_price,
            "total_value": total_value,
            "cpse_count": len(cpse_breakdown),
            "cpse_breakdown": cpse_breakdown,
            "is_duplicate_stock": is_duplicate_stock,
            "mapped_materials_count": len(mat_ids)
        })

    return records

def compute_system_alerts(db: Session) -> List[Dict[str, Any]]:
    """
    Computes all active system alerts:
    - OUT OF STOCK (available == 0)
    - LOW STOCK (available < reorder level)
    - OVERSTOCK (available > 3x reorder level)
    - DUPLICATE INVENTORY (2+ CPSEs holding stock)
    - SPECIFICATION CONFLICT (matches flagged with dimension mismatch)
    - PENDING HUMAN REVIEW (unresolved candidate matches)
    """
    alerts = []

    # 1. Out of stock and Low Stock from raw/mapped inventory
    inventories = db.query(Inventory).all()
    for inv in inventories:
        mat = inv.material
        if not mat:
            continue
        wh = inv.warehouse.name if inv.warehouse else "Warehouse"

        if inv.available_qty <= 0:
            alerts.append({
                "type": "OUT OF STOCK",
                "severity": "Critical",
                "title": f"Stock Depleted: {mat.cpse} - {mat.legacy_code}",
                "description": f"Available stock is 0 {mat.uom} at {wh}. Urgent procurement review required.",
                "entity": f"{mat.cpse}:{mat.legacy_code}"
            })
        elif inv.reorder_level > 0 and inv.available_qty < inv.reorder_level:
            alerts.append({
                "type": "LOW STOCK",
                "severity": "Warning",
                "title": f"Low Stock Threshold: {mat.cpse} - {mat.legacy_code}",
                "description": f"Available: {inv.available_qty} {mat.uom} below reorder level ({inv.reorder_level} {mat.uom}) at {wh}.",
                "entity": f"{mat.cpse}:{mat.legacy_code}"
            })
        elif inv.reorder_level > 0 and inv.available_qty > (inv.reorder_level * 3):
            alerts.append({
                "type": "OVERSTOCK",
                "severity": "Info",
                "title": f"Overstock Detected: {mat.cpse} - {mat.legacy_code}",
                "description": f"Available {inv.available_qty} {mat.uom} exceeds 3x reorder level ({inv.reorder_level} {mat.uom}) at {wh}. Potential excess capital tie-up.",
                "entity": f"{mat.cpse}:{mat.legacy_code}"
            })

    # 2. Duplicate Inventory alerts from Harmonized Materials
    agg = get_harmonized_inventory_aggregation(db)
    for item in agg:
        if item["is_duplicate_stock"]:
            cpse_names = list(item["cpse_breakdown"].keys())
            total_avail = item["total_available"]
            uom = item["uom"] or "units"
            alerts.append({
                "type": "DUPLICATE INVENTORY",
                "severity": "Warning",
                "title": f"Cross-CPSE Duplicate Stock: {item['common_code']}",
                "description": f"Simultaneous stock held across {len(cpse_names)} CPSEs ({', '.join(cpse_names)}) totaling {total_avail} {uom}. Procurement can be deferred or shared.",
                "entity": item["common_code"]
            })

    # 3. Specification Conflict alerts from Match Results
    conflicts = db.query(MatchResult).filter(
        MatchResult.match_type == "SIMILAR_NOT_EQUIVALENT",
        MatchResult.explanation_text.like("%Specification Conflict%")
    ).all()
    for conf in conflicts:
        ma = conf.material_a
        mb = conf.material_b
        alerts.append({
            "type": "SPECIFICATION CONFLICT",
            "severity": "Warning",
            "title": f"Specification Conflict: {ma.cpse}:{ma.legacy_code} vs {mb.cpse}:{mb.legacy_code}",
            "description": f"High semantic similarity but incompatible physical attributes detected. Harmonization prevented.",
            "entity": f"{ma.legacy_code} / {mb.legacy_code}"
        })

    # 4. Pending Human Review alerts
    pending_count = db.query(MatchResult).filter(MatchResult.status == "pending").count()
    if pending_count > 0:
        alerts.append({
            "type": "PENDING HUMAN REVIEW",
            "severity": "Info",
            "title": f"{pending_count} Candidate Matches Awaiting Review",
            "description": "Harmonization engine identified candidate matches requiring Procurement Officer validation.",
            "entity": f"{pending_count} items"
        })

    return alerts
