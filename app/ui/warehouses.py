import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from app.database.models import Warehouse, Inventory
from app.utils.formatting import format_inr

def render_warehouses_page(db: Session):
    st.title("Warehouse Directory & Storage Distribution")
    st.caption("Distribution centers and refinery storage depots across CPSEs")

    warehouses = db.query(Warehouse).all()
    if not warehouses:
        st.info("No warehouses registered. Load the demo dataset to view storage depots.")
        return

    wh_data = []
    for wh in warehouses:
        invs = wh.inventories
        total_items = len(invs)
        total_stock = sum(i.available_qty for i in invs)
        total_val = sum(i.available_qty * (i.material.unit_price if i.material else 0) for i in invs)

        wh_data.append({
            "Warehouse Name": wh.name,
            "CPSE": wh.cpse,
            "Location": wh.location,
            "Distinct SKUs": total_items,
            "Total Available Units": f"{total_stock:,.0f}",
            "Total Inventory Valuation": format_inr(total_val)
        })

    st.dataframe(pd.DataFrame(wh_data), use_container_width=True, hide_index=True)
