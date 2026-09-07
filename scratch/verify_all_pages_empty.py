import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.db import SessionLocal
from app.database.models import Material, MatchGroup, Inventory
from app.services.analytics.financial_analytics import compute_financial_analytics
from app.services.analytics.inventory_analytics import get_harmonized_inventory_aggregation, compute_system_alerts
from app.services.export.export_service import generate_harmonized_materials_excel

def test_pages_empty():
    db = SessionLocal()
    assert db.query(Material).count() == 0
    assert db.query(MatchGroup).count() == 0
    assert db.query(Inventory).count() == 0

    print("Checking financial analytics on empty DB...")
    fin = compute_financial_analytics(db)
    assert fin["total_inventory_value"] == 0.0
    print("Financial analytics handles empty DB cleanly.")

    print("Checking inventory aggregation on empty DB...")
    agg = get_harmonized_inventory_aggregation(db)
    assert len(agg) == 0
    print("Inventory aggregation handles empty DB cleanly.")

    print("Checking system alerts on empty DB...")
    alerts = compute_system_alerts(db)
    assert len(alerts) == 0
    print("System alerts handles empty DB cleanly.")

    print("Checking export service on empty DB...")
    excel_bytes, filename, count = generate_harmonized_materials_excel(db)
    assert count == 0
    print("Export service handles empty DB cleanly.")

    db.close()
    print("All empty state checks passed successfully!")

if __name__ == "__main__":
    test_pages_empty()
