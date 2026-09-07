import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from app.database.models import Supplier, Inventory

def render_suppliers_page(db: Session):
    st.title("Supplier Directory & Multi-CPSE Supply Analysis")
    st.caption("Identify common vendors supplying identical or equivalent materials across different CPSEs")

    suppliers = db.query(Supplier).all()
    if not suppliers:
        st.info("No suppliers registered. Load the demo dataset to view suppliers.")
        return

    sup_data = []
    for sup in suppliers:
        invs = sup.inventories
        cpses_supplied = list(set(inv.material.cpse for inv in invs if inv.material))
        materials_count = len(invs)

        sup_data.append({
            "Supplier Name": sup.name,
            "Contact Info": sup.contact_info or "N/A",
            "CPSEs Supplied": ", ".join(cpses_supplied) if cpses_supplied else "None",
            "CPSE Count": len(cpses_supplied),
            "Supplied SKUs": materials_count
        })

    st.dataframe(pd.DataFrame(sup_data), use_container_width=True, hide_index=True)
