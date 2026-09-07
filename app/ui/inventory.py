import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from app.services.analytics.inventory_analytics import get_harmonized_inventory_aggregation
from app.database.models import Inventory, Material, Warehouse
from app.utils.formatting import format_inr

def render_inventory_page(db: Session):
    st.title("Cross-CPSE Inventory Aggregation")
    st.caption("Aggregated stock visibility across Central Public Sector Enterprises to prevent redundant procurement")

    if db.query(Material).count() == 0:
        st.info("No materials loaded yet — please upload a file or load the demo dataset to view multi-CPSE inventory.")
        return

    tab_harm, tab_all = st.tabs([
        "🌐 Harmonized Stock View (Cross-CPSE)",
        "📦 Legacy Warehouse Stock List"
    ])

    with tab_harm:
        st.subheader("Harmonized Material Aggregation")
        st.markdown(
            "> [!TIP]\n"
            "> **Key Procurement Insight:** When multiple CPSEs hold duplicate stock for the same standardized material, "
            "> inter-enterprise transfer or inventory consolidation can defer new procurement tenders."
        )

        agg_data = get_harmonized_inventory_aggregation(db)
        if not agg_data:
            st.info("No harmonized materials found. Review and approve candidate matches in 'AI Harmonization' to see cross-CPSE aggregated stock.")
        else:
            table_rows = []
            for item in agg_data:
                cpse_summary = []
                for cpse, details in item["cpse_breakdown"].items():
                    cpse_summary.append(f"{cpse}: {details['available']} {item['uom']}")
                cpse_str = " | ".join(cpse_summary)

                table_rows.append({
                    "Common Material Code": item["common_code"],
                    "Standard Description": item["standard_description"],
                    "Category": item["category"],
                    "Total Available Stock": f"{item['total_available']:,.0f} {item['uom']}",
                    "CPSE Holding Stock": f"{item['cpse_count']} CPSE(s)",
                    "CPSE Breakdown": cpse_str,
                    "Total Value (INR)": format_inr(item["total_value"]),
                    "Duplicate Status": "⚠️ Duplicate Stock" if item["is_duplicate_stock"] else "Unique Stock"
                })

            df = pd.DataFrame(table_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_all:
        st.subheader("All Warehouse Inventory Positions")
        inventories = db.query(Inventory).all()
        raw_rows = []
        for inv in inventories:
            mat = inv.material
            wh = inv.warehouse
            raw_rows.append({
                "CPSE": mat.cpse if mat else "",
                "Legacy Code": mat.legacy_code if mat else "",
                "Description": mat.raw_description if mat else "",
                "Warehouse": wh.name if wh else "",
                "Location": wh.location if wh else "",
                "Available Qty": f"{inv.available_qty:,.0f}",
                "Reserved Qty": f"{inv.reserved_qty:,.0f}",
                "On Order Qty": f"{inv.on_order_qty:,.0f}",
                "Reorder Level": f"{inv.reorder_level:,.0f}",
                "Unit Price": format_inr(mat.unit_price) if mat else "₹0",
                "Total Value": format_inr(inv.available_qty * (mat.unit_price if mat else 0))
            })

        if raw_rows:
            st.dataframe(pd.DataFrame(raw_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No warehouse stock records loaded.")
