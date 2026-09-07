import pandas as pd
from typing import Tuple, Dict, Any, List

EXPECTED_COLUMNS = [
    "CPSE",
    "Legacy Material Code",
    "Raw Material Description",
    "Category",
    "Subcategory",
    "Material",
    "Specification",
    "Dimensions",
    "UOM",
    "Unit Price",
    "Available Quantity",
    "Reserved Quantity",
    "On Order Quantity",
    "Reorder Level",
    "Warehouse",
    "Supplier"
]

REQUIRED_COLUMNS = [
    "CPSE",
    "Legacy Material Code",
    "Raw Material Description"
]

OPTIONAL_COLUMNS = [col for col in EXPECTED_COLUMNS if col not in REQUIRED_COLUMNS]
ALL_EXPECTED_COLUMNS = EXPECTED_COLUMNS

def validate_dataframe(df: pd.DataFrame, check_all_expected: bool = True) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Validates ingested material dataframe.
    Checks that expected columns are present, removes exact duplicates,
    validates row-level fields, and aggregates statistics.
    Returns cleaned DataFrame and a summary dictionary.
    Never throws unhandled exceptions.
    """
    report = {
        "records_loaded": 0,
        "valid_records": 0,
        "missing_fields": 0,
        "invalid_records": 0,
        "duplicate_rows": 0,
        "missing_columns": [],
        "warnings": [],
        "errors": []
    }

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        report["errors"].append("The uploaded file contains no data or could not be parsed.")
        return pd.DataFrame(), report

    report["records_loaded"] = len(df)

    # Normalize column names: strip whitespace, case-insensitive match
    col_map = {}
    for col in df.columns:
        col_clean = str(col).strip()
        matched = False
        for exp in ALL_EXPECTED_COLUMNS:
            if col_clean.lower() == exp.lower():
                col_map[col] = exp
                matched = True
                break
        if not matched:
            col_map[col] = col_clean

    df = df.rename(columns=col_map)

    # Check for expected columns
    cols_to_check = EXPECTED_COLUMNS if check_all_expected else REQUIRED_COLUMNS
    missing_cols = [col for col in cols_to_check if col not in df.columns]
    if missing_cols:
        report["missing_columns"] = missing_cols
        report["errors"].append(f"Missing required columns: {', '.join(missing_cols)}")
        return pd.DataFrame(), report

    # Check for exact duplicate rows
    initial_count = len(df)
    df_dedup = df.drop_duplicates()
    dupe_count = initial_count - len(df_dedup)
    if dupe_count > 0:
        report["duplicate_rows"] = dupe_count
        report["warnings"].append(f"Found and removed {dupe_count} exact duplicate rows.")
    df = df_dedup.copy()

    # Fill optional missing columns if any wasn't checked
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            if "Quantity" in col or "Price" in col or "Level" in col:
                df[col] = 0.0
            else:
                df[col] = ""


    # Sanitize rows
    valid_rows: List[dict] = []
    for idx, row in df.iterrows():
        cpse = str(row.get("CPSE", "") or "").strip()
        legacy_code = str(row.get("Legacy Material Code", "") or "").strip()
        desc = str(row.get("Raw Material Description", "") or "").strip()

        if not cpse or not legacy_code or not desc:
            report["invalid_records"] += 1
            missing_parts = []
            if not cpse: missing_parts.append("CPSE")
            if not legacy_code: missing_parts.append("Legacy Material Code")
            if not desc: missing_parts.append("Raw Material Description")
            report["warnings"].append(f"Row {idx+1}: Missing essential field(s) ({', '.join(missing_parts)}). Row skipped.")
            continue

        # Check numeric fields
        try:
            unit_price = float(row.get("Unit Price", 0.0) or 0.0)
        except (ValueError, TypeError):
            unit_price = 0.0

        try:
            avail_qty = float(row.get("Available Quantity", 0.0) or 0.0)
        except (ValueError, TypeError):
            avail_qty = 0.0

        try:
            res_qty = float(row.get("Reserved Quantity", 0.0) or 0.0)
        except (ValueError, TypeError):
            res_qty = 0.0

        try:
            order_qty = float(row.get("On Order Quantity", 0.0) or 0.0)
        except (ValueError, TypeError):
            order_qty = 0.0

        try:
            reorder_lvl = float(row.get("Reorder Level", 0.0) or 0.0)
        except (ValueError, TypeError):
            reorder_lvl = 0.0

        # Check missing non-critical fields
        uom = str(row.get("UOM", "") or "").strip()
        dims = str(row.get("Dimensions", "") or "").strip()
        if not uom or not dims:
            report["missing_fields"] += 1

        clean_row = {
            "CPSE": cpse,
            "Legacy Material Code": legacy_code,
            "Raw Material Description": desc,
            "Category": str(row.get("Category", "") or "").strip(),
            "Subcategory": str(row.get("Subcategory", "") or "").strip(),
            "Material": str(row.get("Material", "") or "").strip(),
            "Specification": str(row.get("Specification", "") or "").strip(),
            "Dimensions": dims,
            "UOM": uom if uom else "NOS",
            "Unit Price": unit_price,
            "Available Quantity": avail_qty,
            "Reserved Quantity": res_qty,
            "On Order Quantity": order_qty,
            "Reorder Level": reorder_lvl,
            "Warehouse": str(row.get("Warehouse", "") or "").strip() or f"{cpse}-Central-Depot",
            "Supplier": str(row.get("Supplier", "") or "").strip() or "Standard CPSE Vendor"
        }
        valid_rows.append(clean_row)

    cleaned_df = pd.DataFrame(valid_rows)
    report["valid_records"] = len(cleaned_df)
    return cleaned_df, report
