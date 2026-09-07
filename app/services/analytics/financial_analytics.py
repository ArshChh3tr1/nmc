from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.config import get_weights_config
from app.database.models import Material, HarmonizedMaterial, Inventory, MaterialMapping
from app.services.analytics.inventory_analytics import get_harmonized_inventory_aggregation

def compute_financial_analytics(db: Session) -> Dict[str, Any]:
    """
    Computes financial metrics with prototype assumption formulas.
    All figures are labeled 'Prototype Estimate'.
    """
    cfg = get_weights_config().get("financial_assumptions", {})
    wc_release_pct = float(cfg.get("working_capital_release_pct", 0.35))
    avoidable_proc_pct = float(cfg.get("avoidable_procurement_pct", 0.25))
    holding_cost_pct = float(cfg.get("holding_cost_annual_pct", 0.18))

    # 1. Total inventory value & breakdown by CPSE / Category
    inventories = db.query(Inventory).all()
    total_inventory_val = 0.0
    val_by_cpse: Dict[str, float] = {}
    val_by_category: Dict[str, float] = {}

    for inv in inventories:
        mat = inv.material
        if not mat:
            continue
        price = mat.unit_price or 0.0
        val = inv.available_qty * price
        total_inventory_val += val

        cpse = mat.cpse or "Unknown"
        val_by_cpse[cpse] = val_by_cpse.get(cpse, 0.0) + val

        cat_name = mat.category.name if mat.category else "General"
        val_by_category[cat_name] = val_by_category.get(cat_name, 0.0) + val

    # 2. Duplicate inventory value
    # Portion of inventory for harmonized materials stocked simultaneously by 2+ CPSEs
    agg_harmonized = get_harmonized_inventory_aggregation(db)
    duplicate_inventory_val = 0.0
    duplicate_val_by_category: Dict[str, float] = {}
    duplicate_count_by_cpse: Dict[str, int] = {}

    for item in agg_harmonized:
        if item["is_duplicate_stock"]:
            d_val = item["total_value"]
            duplicate_inventory_val += d_val
            cat = item["category"]
            duplicate_val_by_category[cat] = duplicate_val_by_category.get(cat, 0.0) + d_val

            for cpse_k in item["cpse_breakdown"].keys():
                duplicate_count_by_cpse[cpse_k] = duplicate_count_by_cpse.get(cpse_k, 0) + 1

    # 3. Working capital release & Avoidable procurement
    working_capital_release = duplicate_inventory_val * wc_release_pct
    annual_holding_cost_savings = duplicate_inventory_val * holding_cost_pct
    avoidable_procurement = duplicate_inventory_val * avoidable_proc_pct

    # Avoidable procurement by category
    avoidable_by_category = {
        cat: val * avoidable_proc_pct for cat, val in duplicate_val_by_category.items()
    }

    total_potential_savings = working_capital_release + annual_holding_cost_savings

    return {
        "disclaimer": "Prototype Estimate — Based on configurable mathematical assumptions",
        "total_inventory_value": round(total_inventory_val, 2),
        "duplicate_inventory_value": round(duplicate_inventory_val, 2),
        "potential_working_capital_release": round(working_capital_release, 2),
        "annual_holding_cost_savings": round(annual_holding_cost_savings, 2),
        "avoidable_procurement_value": round(avoidable_procurement, 2),
        "total_potential_savings": round(total_potential_savings, 2),
        "value_by_cpse": {k: round(v, 2) for k, v in val_by_cpse.items()},
        "value_by_category": {k: round(v, 2) for k, v in val_by_category.items()},
        "duplicate_val_by_category": {k: round(v, 2) for k, v in duplicate_val_by_category.items()},
        "duplicate_count_by_cpse": duplicate_count_by_cpse,
        "avoidable_by_category": {k: round(v, 2) for k, v in avoidable_by_category.items()},
        "assumptions": {
            "wc_release_pct": wc_release_pct * 100,
            "avoidable_proc_pct": avoidable_proc_pct * 100,
            "holding_cost_pct": holding_cost_pct * 100,
        }
    }
