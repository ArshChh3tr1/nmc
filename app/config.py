import os
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "nmc_harmonizer.db"
DB_URL = f"sqlite:///{DB_PATH}"

def load_yaml(file_path: Path) -> dict:
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_yaml(file_path: Path, data: dict) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

def get_weights_config() -> dict:
    weights_path = CONFIG_DIR / "weights.yaml"
    data = load_yaml(weights_path)
    default_weights = {
        "semantic_similarity": 0.40,
        "material_match": 0.20,
        "dimension_match": 0.15,
        "category_match": 0.10,
        "specification_match": 0.10,
        "uom_match": 0.05,
    }
    default_thresholds = {
        "exact_duplicate_min": 95.0,
        "high_confidence_min": 90.0,
        "medium_confidence_min": 80.0,
        "low_confidence_min": 60.0,
    }
    default_financial = {
        "working_capital_release_pct": 0.35,
        "avoidable_procurement_pct": 0.25,
        "holding_cost_annual_pct": 0.18,
    }
    default_auto_approve = {
        "enabled": True,
        "threshold": 95.0,
    }
    weights = data.get("weights", default_weights)
    thresholds = data.get("thresholds", default_thresholds)
    financial = data.get("financial_assumptions", default_financial)
    auto_approve = data.get("auto_approve", default_auto_approve)
    return {
        "weights": weights,
        "thresholds": thresholds,
        "financial_assumptions": financial,
        "auto_approve": auto_approve,
    }

def update_weights_config(weights: dict = None, thresholds: dict = None, financial: dict = None, auto_approve: dict = None) -> None:
    weights_path = CONFIG_DIR / "weights.yaml"
    current = get_weights_config()
    if weights:
        current["weights"].update(weights)
    if thresholds:
        current["thresholds"].update(thresholds)
    if financial:
        current["financial_assumptions"].update(financial)
    if auto_approve:
        current["auto_approve"].update(auto_approve)
    save_yaml(weights_path, current)

def get_taxonomy_config() -> dict:
    tax_path = CONFIG_DIR / "taxonomy.yaml"
    return load_yaml(tax_path)

def update_taxonomy_config(taxonomy_data: dict) -> None:
    tax_path = CONFIG_DIR / "taxonomy.yaml"
    save_yaml(tax_path, taxonomy_data)

def get_normalization_dict() -> dict:
    norm_path = CONFIG_DIR / "normalization_dict.yaml"
    return load_yaml(norm_path)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K_CANDIDATES = 20
DEMO_DATASET_PATH = DATA_DIR / "demo_dataset.xlsx"
