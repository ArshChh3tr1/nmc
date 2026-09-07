import os
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from app.config import DEMO_DATASET_PATH, get_taxonomy_config
from app.database.models import Category, Warehouse, Supplier
from app.services.ingestion.file_loader import ingest_material_file
from app.services.audit.audit_logger import log_action

def ensure_demo_excel_file() -> Path:
    """
    Creates a rich synthetic demo_dataset.xlsx if it does not exist,
    matching the exact sheet structure:
    Material_Master, Ground_Truth, Taxonomy, Warehouses, Suppliers.
    """
    DEMO_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 1. Material Master
    material_data = [
        # Hex Bolts duplicate group across 4 CPSEs (M16 x 50)
        {"CPSE": "IOCL", "Legacy Material Code": "IO-FST-48392", "Raw Material Description": "HEX BOLT SS M16 X 50", "Category": "Fasteners", "Subcategory": "Hex Bolts", "Material": "Stainless Steel", "Specification": "ISO 4017", "Dimensions": "M16 X 50", "UOM": "NOS", "Unit Price": 125.0, "Available Quantity": 4500, "Reserved Quantity": 500, "On Order Quantity": 1000, "Reorder Level": 1500, "Warehouse": "IOCL Panipat Refinery Store", "Supplier": "Apex Fasteners India"},
        {"CPSE": "BPCL", "Legacy Material Code": "BP-FST-99213", "Raw Material Description": "SS HEXAGONAL BOLT 16MM X 50MM", "Category": "Fasteners", "Subcategory": "Hex Bolts", "Material": "Stainless Steel", "Specification": "ISO 4017", "Dimensions": "16mm X 50mm", "UOM": "NOS", "Unit Price": 128.5, "Available Quantity": 3200, "Reserved Quantity": 200, "On Order Quantity": 500, "Reorder Level": 1200, "Warehouse": "BPCL Mumbai Refinery Store", "Supplier": "Precision Fasteners Corp"},
        {"CPSE": "HPCL", "Legacy Material Code": "HP-FST-18372", "Raw Material Description": "STAINLESS STEEL HEX BOLT M16-50", "Category": "Fasteners", "Subcategory": "Hex Bolts", "Material": "Stainless Steel", "Specification": "ISO 4017", "Dimensions": "M16-50", "UOM": "NOS", "Unit Price": 124.0, "Available Quantity": 2800, "Reserved Quantity": 400, "On Order Quantity": 800, "Reorder Level": 1000, "Warehouse": "HPCL Visakhapatnam Store", "Supplier": "Sterling Industrial Tools"},
        {"CPSE": "GAIL", "Legacy Material Code": "GA-FST-66291", "Raw Material Description": "HEX HEAD BOLT SS M16X50 ISO 4017", "Category": "Fasteners", "Subcategory": "Hex Bolts", "Material": "Stainless Steel", "Specification": "ISO 4017", "Dimensions": "M16 X 50", "UOM": "NOS", "Unit Price": 126.0, "Available Quantity": 2100, "Reserved Quantity": 150, "On Order Quantity": 400, "Reorder Level": 800, "Warehouse": "GAIL Vijaipur Plant Store", "Supplier": "Apex Fasteners India"},

        # Deliberate Dimension Conflict Trap (M16 x 80 - Length Conflict!)
        {"CPSE": "ONGC", "Legacy Material Code": "ON-FST-77182", "Raw Material Description": "SS HEX BOLT M16 X 80", "Category": "Fasteners", "Subcategory": "Hex Bolts", "Material": "Stainless Steel", "Specification": "ISO 4017", "Dimensions": "M16 X 80", "UOM": "NOS", "Unit Price": 185.0, "Available Quantity": 1500, "Reserved Quantity": 100, "On Order Quantity": 0, "Reorder Level": 500, "Warehouse": "ONGC Hazira Supply Base", "Supplier": "Apex Fasteners India"},

        # Ball Bearings duplicate group across 3 CPSEs (6205-2RS)
        {"CPSE": "IOCL", "Legacy Material Code": "IO-BRG-10291", "Raw Material Description": "DEEP GROOVE BALL BEARING 6205-2RS SKF", "Category": "Bearings", "Subcategory": "Ball Bearings", "Material": "Chrome Steel", "Specification": "DIN 625", "Dimensions": "6205-2RS", "UOM": "NOS", "Unit Price": 850.0, "Available Quantity": 650, "Reserved Quantity": 50, "On Order Quantity": 100, "Reorder Level": 200, "Warehouse": "IOCL Mathura Refinery Store", "Supplier": "SKF Authorized CPSE Distributor"},
        {"CPSE": "BPCL", "Legacy Material Code": "BP-BRG-33910", "Raw Material Description": "BRG BALL 6205 2RS", "Category": "Bearings", "Subcategory": "Ball Bearings", "Material": "Chrome Steel", "Specification": "DIN 625", "Dimensions": "6205-2RS", "UOM": "NOS", "Unit Price": 840.0, "Available Quantity": 420, "Reserved Quantity": 30, "On Order Quantity": 80, "Reorder Level": 150, "Warehouse": "BPCL Kochi Refinery Store", "Supplier": "National Bearing Spares"},
        {"CPSE": "HPCL", "Legacy Material Code": "HP-BRG-55102", "Raw Material Description": "BALL BRG 6205-2RS", "Category": "Bearings", "Subcategory": "Ball Bearings", "Material": "Chrome Steel", "Specification": "DIN 625", "Dimensions": "6205-2RS", "UOM": "NOS", "Unit Price": 860.0, "Available Quantity": 510, "Reserved Quantity": 60, "On Order Quantity": 50, "Reorder Level": 180, "Warehouse": "HPCL Mumbai Terminal", "Supplier": "SKF Authorized CPSE Distributor"},

        # Ball Valves duplicate group across 2 CPSEs (2 inch Class 150)
        {"CPSE": "GAIL", "Legacy Material Code": "GA-VLV-88219", "Raw Material Description": "BALL VALVE 2 INCH 150# CS FLANGED WCB", "Category": "Valves", "Subcategory": "Ball Valves", "Material": "Carbon Steel", "Specification": "API 6D", "Dimensions": "2 INCH CLASS 150", "UOM": "NOS", "Unit Price": 14500.0, "Available Quantity": 75, "Reserved Quantity": 10, "On Order Quantity": 20, "Reorder Level": 25, "Warehouse": "GAIL Vijaipur Plant Store", "Supplier": "L&T Valves Division"},
        {"CPSE": "ONGC", "Legacy Material Code": "ON-VLV-11928", "Raw Material Description": "CS BALL VALVE 50 NB CLASS 150 FLG", "Category": "Valves", "Subcategory": "Ball Valves", "Material": "Carbon Steel", "Specification": "API 6D", "Dimensions": "50 NB 150#", "UOM": "NOS", "Unit Price": 14200.0, "Available Quantity": 60, "Reserved Quantity": 5, "On Order Quantity": 15, "Reorder Level": 20, "Warehouse": "ONGC Uran Plant Store", "Supplier": "Microfinish Valves"},

        # Carbon Steel Pipes duplicate group across 2 CPSEs (2 inch Sch 40 A106-B)
        {"CPSE": "IOCL", "Legacy Material Code": "IO-PIP-00129", "Raw Material Description": "SEAMLESS PIPE CS ASTM A106 GR B 2 INCH SCH 40", "Category": "Pipes", "Subcategory": "Carbon Steel Pipes", "Material": "Carbon Steel", "Specification": "ASTM A106 GR B", "Dimensions": "2 INCH SCH 40", "UOM": "MTR", "Unit Price": 950.0, "Available Quantity": 3200, "Reserved Quantity": 400, "On Order Quantity": 600, "Reorder Level": 1000, "Warehouse": "IOCL Paradip Refinery Store", "Supplier": "Jindal Saw Seamless Pipes"},
        {"CPSE": "BPCL", "Legacy Material Code": "BP-PIP-77218", "Raw Material Description": "CARBON STEEL SMLS PIPE 2\" NB SCH.40 A106-B", "Category": "Pipes", "Subcategory": "Carbon Steel Pipes", "Material": "Carbon Steel", "Specification": "ASTM A106 GR B", "Dimensions": "2\" NB SCH 40", "UOM": "MTR", "Unit Price": 965.0, "Available Quantity": 2100, "Reserved Quantity": 250, "On Order Quantity": 300, "Reorder Level": 800, "Warehouse": "BPCL Mumbai Refinery Store", "Supplier": "Maharashtra Seamless Ltd"},

        # Electrical XLPE Power Cables (3 Core x 2.5 sqmm)
        {"CPSE": "HPCL", "Legacy Material Code": "HP-ELE-90182", "Raw Material Description": "XLPE POWER CABLE 3C X 2.5 SQMM COPPER ARMOURED", "Category": "Electrical", "Subcategory": "Power Cables", "Material": "Copper", "Specification": "IS 7098", "Dimensions": "3C X 2.5 SQMM", "UOM": "MTR", "Unit Price": 280.0, "Available Quantity": 5400, "Reserved Quantity": 600, "On Order Quantity": 1000, "Reorder Level": 1500, "Warehouse": "HPCL Visakhapatnam Store", "Supplier": "Polycab Wires & Cables"},
        {"CPSE": "IOCL", "Legacy Material Code": "IO-ELE-66381", "Raw Material Description": "3C X 2.5 SQ.MM CU ARMOURED XLPE CABLE", "Category": "Electrical", "Subcategory": "Power Cables", "Material": "Copper", "Specification": "IS 7098", "Dimensions": "3C X 2.5 SQMM", "UOM": "MTR", "Unit Price": 285.0, "Available Quantity": 4100, "Reserved Quantity": 300, "On Order Quantity": 500, "Reorder Level": 1200, "Warehouse": "IOCL Panipat Refinery Store", "Supplier": "Havells India Industrial"},

        # Pressure Gauges
        {"CPSE": "GAIL", "Legacy Material Code": "GA-INS-20381", "Raw Material Description": "PRESSURE GAUGE 0-10 BAR DIAL 100MM 1/2 INCH NPT", "Category": "Instrumentation", "Subcategory": "Pressure Gauges", "Material": "Stainless Steel", "Specification": "EN 837-1", "Dimensions": "0-10 BAR 100MM", "UOM": "NOS", "Unit Price": 3400.0, "Available Quantity": 45, "Reserved Quantity": 5, "On Order Quantity": 10, "Reorder Level": 15, "Warehouse": "GAIL Vijaipur Plant Store", "Supplier": "WIKA Instruments India"},
        {"CPSE": "HPCL", "Legacy Material Code": "HP-INS-11293", "Raw Material Description": "DIAL PRESSURE GAUGE 0 TO 10 BAR SS316", "Category": "Instrumentation", "Subcategory": "Pressure Gauges", "Material": "Stainless Steel", "Specification": "EN 837-1", "Dimensions": "0-10 BAR", "UOM": "NOS", "Unit Price": 3550.0, "Available Quantity": 35, "Reserved Quantity": 2, "On Order Quantity": 10, "Reorder Level": 10, "Warehouse": "HPCL Mumbai Terminal", "Supplier": "Baumer Technologies"},

        # Safety PPE
        {"CPSE": "IOCL", "Legacy Material Code": "IO-SAF-44102", "Raw Material Description": "INDUSTRIAL SAFETY HELMET HDPE WHITE WITH RATCHET", "Category": "Safety", "Subcategory": "Safety Helmets", "Material": "HDPE", "Specification": "IS 2925", "Dimensions": "Standard", "UOM": "NOS", "Unit Price": 380.0, "Available Quantity": 850, "Reserved Quantity": 100, "On Order Quantity": 200, "Reorder Level": 300, "Warehouse": "IOCL Panipat Refinery Store", "Supplier": "Karam Safety Instruments"},
        {"CPSE": "BPCL", "Legacy Material Code": "BP-SAF-88392", "Raw Material Description": "SAFETY HELMET WHITE HDPE IS:2925", "Category": "Safety", "Subcategory": "Safety Helmets", "Material": "HDPE", "Specification": "IS 2925", "Dimensions": "Standard", "UOM": "NOS", "Unit Price": 375.0, "Available Quantity": 620, "Reserved Quantity": 50, "On Order Quantity": 150, "Reorder Level": 250, "Warehouse": "BPCL Kochi Refinery Store", "Supplier": "Udyogi Safety Appliances"}
    ]

    # 2. Ground Truth for Offline AI Evaluation
    ground_truth_data = [
        {"Material_A": "IO-FST-48392", "Material_B": "BP-FST-99213", "Expected_Match": "DUPLICATE", "Notes": "Identical M16 x 50 SS Bolt"},
        {"Material_A": "IO-FST-48392", "Material_B": "HP-FST-18372", "Expected_Match": "DUPLICATE", "Notes": "Identical M16 x 50 SS Bolt"},
        {"Material_A": "BP-FST-99213", "Material_B": "HP-FST-18372", "Expected_Match": "DUPLICATE", "Notes": "Identical M16 x 50 SS Bolt"},
        {"Material_A": "IO-FST-48392", "Material_B": "GA-FST-66291", "Expected_Match": "DUPLICATE", "Notes": "Identical M16 x 50 SS Bolt"},
        {"Material_A": "BP-FST-99213", "Material_B": "GA-FST-66291", "Expected_Match": "DUPLICATE", "Notes": "Identical M16 x 50 SS Bolt"},
        {"Material_A": "HP-FST-18372", "Material_B": "GA-FST-66291", "Expected_Match": "DUPLICATE", "Notes": "Identical M16 x 50 SS Bolt"},
        {"Material_A": "IO-FST-48392", "Material_B": "ON-FST-77182", "Expected_Match": "CONFLICT", "Notes": "Dimension conflict: 50mm vs 80mm length"},
        {"Material_A": "GA-FST-66291", "Material_B": "ON-FST-77182", "Expected_Match": "CONFLICT", "Notes": "Dimension conflict: 50mm vs 80mm length"},
        {"Material_A": "IO-BRG-10291", "Material_B": "BP-BRG-33910", "Expected_Match": "DUPLICATE", "Notes": "Identical 6205-2RS Ball Bearing"},
        {"Material_A": "IO-BRG-10291", "Material_B": "HP-BRG-55102", "Expected_Match": "DUPLICATE", "Notes": "Identical 6205-2RS Ball Bearing"},
        {"Material_A": "BP-BRG-33910", "Material_B": "HP-BRG-55102", "Expected_Match": "DUPLICATE", "Notes": "Identical 6205-2RS Ball Bearing"},
        {"Material_A": "GA-VLV-88219", "Material_B": "ON-VLV-11928", "Expected_Match": "DUPLICATE", "Notes": "Identical 2 inch Class 150 CS Ball Valve"},
        {"Material_A": "IO-PIP-00129", "Material_B": "BP-PIP-77218", "Expected_Match": "DUPLICATE", "Notes": "Identical 2 inch Sch 40 CS Seamless Pipe"},
        {"Material_A": "HP-ELE-90182", "Material_B": "IO-ELE-66381", "Expected_Match": "DUPLICATE", "Notes": "Identical 3C x 2.5 sqmm XLPE Cable"},
        {"Material_A": "GA-INS-20381", "Material_B": "HP-INS-11293", "Expected_Match": "EQUIVALENT", "Notes": "Functionally equivalent 0-10 bar pressure gauge"},
        {"Material_A": "IO-SAF-44102", "Material_B": "BP-SAF-88392", "Expected_Match": "DUPLICATE", "Notes": "Identical IS 2925 HDPE White Helmet"}
    ]

    # 3. Warehouses
    warehouses_data = [
        {"Name": "IOCL Panipat Refinery Store", "CPSE": "IOCL", "Location": "Panipat, Haryana"},
        {"Name": "IOCL Mathura Refinery Store", "CPSE": "IOCL", "Location": "Mathura, UP"},
        {"Name": "IOCL Paradip Refinery Store", "CPSE": "IOCL", "Location": "Paradip, Odisha"},
        {"Name": "BPCL Mumbai Refinery Store", "CPSE": "BPCL", "Location": "Mahul, Mumbai"},
        {"Name": "BPCL Kochi Refinery Store", "CPSE": "BPCL", "Location": "Ambalamugal, Kochi"},
        {"Name": "HPCL Visakhapatnam Store", "CPSE": "HPCL", "Location": "Visakhapatnam, AP"},
        {"Name": "HPCL Mumbai Terminal", "CPSE": "HPCL", "Location": "Sewree, Mumbai"},
        {"Name": "ONGC Hazira Supply Base", "CPSE": "ONGC", "Location": "Surat, Gujarat"},
        {"Name": "ONGC Uran Plant Store", "CPSE": "ONGC", "Location": "Raigad, Maharashtra"},
        {"Name": "GAIL Vijaipur Plant Store", "CPSE": "GAIL", "Location": "Guna, Madhya Pradesh"}
    ]

    # 4. Suppliers
    suppliers_data = [
        {"Name": "Apex Fasteners India", "Contact_Info": "contact@apexfasteners.co.in | Ludhiana"},
        {"Name": "Precision Fasteners Corp", "Contact_Info": "sales@pfc-fasteners.com | Pune"},
        {"Name": "Sterling Industrial Tools", "Contact_Info": "orders@sterlingtools.in | Chennai"},
        {"Name": "SKF Authorized CPSE Distributor", "Contact_Info": "industrial@skf-distributor.in | New Delhi"},
        {"Name": "National Bearing Spares", "Contact_Info": "info@nationalbearings.in | Kolkata"},
        {"Name": "L&T Valves Division", "Contact_Info": "valves@larsentoubro.com | Chennai"},
        {"Name": "Microfinish Valves", "Contact_Info": "support@microfinishvalves.com | Hubli"},
        {"Name": "Jindal Saw Seamless Pipes", "Contact_Info": "pipes@jindalsaw.com | Gurugram"},
        {"Name": "Maharashtra Seamless Ltd", "Contact_Info": "sales@mslpipes.com | Raigad"},
        {"Name": "Polycab Wires & Cables", "Contact_Info": "institutional@polycab.com | Vadodara"},
        {"Name": "Havells India Industrial", "Contact_Info": "industrial@havells.com | Noida"},
        {"Name": "WIKA Instruments India", "Contact_Info": "sales@wika.co.in | Pune"},
        {"Name": "Baumer Technologies", "Contact_Info": "info@baumerindia.com | Mumbai"},
        {"Name": "Karam Safety Instruments", "Contact_Info": "safety@karam.in | Lucknow"},
        {"Name": "Udyogi Safety Appliances", "Contact_Info": "sales@udyogi.com | Kolkata"}
    ]

    # 5. Taxonomy
    taxonomy_data = [
        {"Category": "Fasteners", "Abbrev": "FST", "Subcategory": "Hex Bolts"},
        {"Category": "Fasteners", "Abbrev": "FST", "Subcategory": "Nuts"},
        {"Category": "Fasteners", "Abbrev": "FST", "Subcategory": "Washers"},
        {"Category": "Bearings", "Abbrev": "BRG", "Subcategory": "Ball Bearings"},
        {"Category": "Bearings", "Abbrev": "BRG", "Subcategory": "Roller Bearings"},
        {"Category": "Valves", "Abbrev": "VLV", "Subcategory": "Ball Valves"},
        {"Category": "Valves", "Abbrev": "VLV", "Subcategory": "Gate Valves"},
        {"Category": "Pipes", "Abbrev": "PIP", "Subcategory": "Carbon Steel Pipes"},
        {"Category": "Electrical", "Abbrev": "ELE", "Subcategory": "Power Cables"},
        {"Category": "Instrumentation", "Abbrev": "INS", "Subcategory": "Pressure Gauges"},
        {"Category": "Safety", "Abbrev": "SAF", "Subcategory": "Safety Helmets"}
    ]

    with pd.ExcelWriter(DEMO_DATASET_PATH, engine="openpyxl") as writer:
        pd.DataFrame(material_data).to_excel(writer, sheet_name="Material_Master", index=False)
        pd.DataFrame(ground_truth_data).to_excel(writer, sheet_name="Ground_Truth", index=False)
        pd.DataFrame(taxonomy_data).to_excel(writer, sheet_name="Taxonomy", index=False)
        pd.DataFrame(warehouses_data).to_excel(writer, sheet_name="Warehouses", index=False)
        pd.DataFrame(suppliers_data).to_excel(writer, sheet_name="Suppliers", index=False)

    return DEMO_DATASET_PATH

def load_demo_dataset(db: Session, actor_name: str = "Demo Admin") -> Tuple[bool, str]:
    """
    Loads the bundled demo Excel workbook reliably with one click/command.
    Seeds master tables and material records.
    """
    excel_path = ensure_demo_excel_file()
    try:
        # Load master sheets
        xls = pd.ExcelFile(excel_path)

        # 1. Warehouses
        if "Warehouses" in xls.sheet_names:
            wh_df = pd.read_excel(xls, "Warehouses")
            for _, r in wh_df.iterrows():
                name = str(r.get("Name", "")).strip()
                if not name:
                    continue
                wh = db.query(Warehouse).filter(Warehouse.name == name).first()
                if not wh:
                    wh = Warehouse(
                        name=name,
                        cpse=str(r.get("CPSE", "CPSE")).strip(),
                        location=str(r.get("Location", "")).strip()
                    )
                    db.add(wh)

        # 2. Suppliers
        if "Suppliers" in xls.sheet_names:
            sup_df = pd.read_excel(xls, "Suppliers")
            for _, r in sup_df.iterrows():
                name = str(r.get("Name", "")).strip()
                if not name:
                    continue
                sup = db.query(Supplier).filter(Supplier.name == name).first()
                if not sup:
                    sup = Supplier(
                        name=name,
                        contact_info=str(r.get("Contact_Info", "")).strip()
                    )
                    db.add(sup)

        db.commit()

        # 3. Materials via Material_Master sheet
        success, report = ingest_material_file(
            db=db,
            file_bytes_or_path=str(excel_path),
            file_name="demo_dataset.xlsx",
            actor_name=actor_name
        )

        if success:
            log_action(
                db=db,
                actor=actor_name,
                action="Demo Dataset Loaded",
                entity_type="DemoLoader",
                details=f"Loaded {report['valid_records']} items from demo dataset."
            )
            return True, f"Successfully loaded {report['valid_records']} demo materials across CPSEs (IOCL, BPCL, HPCL, ONGC, GAIL)."
        else:
            return False, f"Ingestion errors: {'; '.join(report.get('errors', []))}"

    except Exception as e:
        return False, f"Failed to load demo dataset: {str(e)}"
