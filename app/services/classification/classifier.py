from typing import Dict, Any, Tuple, Optional
from app.config import get_taxonomy_config

class MaterialClassifier:
    def __init__(self):
        self.reload_taxonomy()

    def reload_taxonomy(self):
        self.taxonomy = get_taxonomy_config()
        self.categories = self.taxonomy.get("categories", [])

    def classify(self, normalized_description: str, material_type: str = "") -> Tuple[str, str, str]:
        """
        Classifies material based on normalized description and extracted material type.
        Returns: (category_name, subcategory_name, category_abbrev)
        """
        text = f"{normalized_description} {material_type}".lower()

        best_category = "General"
        best_abbrev = "GEN"
        best_subcategory = "Uncategorized"
        max_cat_score = 0
        max_subcat_score = 0

        for cat in self.categories:
            cat_name = cat.get("name", "General")
            cat_abbrev = cat.get("abbrev", "GEN")
            cat_keywords = cat.get("keywords", [])

            # Check category level keywords
            cat_score = 0
            for kw in cat_keywords:
                if kw.lower() in text:
                    cat_score += len(kw)

            if cat_score > max_cat_score:
                max_cat_score = cat_score
                best_category = cat_name
                best_abbrev = cat_abbrev
                best_subcategory = "General " + cat_name

                # Now check subcategories
                subcats = cat.get("subcategories", [])
                max_subcat_score = 0
                for subcat in subcats:
                    sub_name = subcat.get("name", "")
                    sub_kws = subcat.get("keywords", [])
                    sub_score = 0
                    for skw in sub_kws:
                        if skw.lower() in text:
                            sub_score += len(skw)
                    if sub_score > max_subcat_score:
                        max_subcat_score = sub_score
                        best_subcategory = sub_name

        # If no strong match found, default to Fasteners if bolt/nut or Bearings if bearing
        if max_cat_score == 0:
            if "bolt" in text or "nut" in text or "washer" in text or "stud" in text:
                return "Fasteners", "Hex Bolts", "FST"
            if "bearing" in text or "brg" in text:
                return "Bearings", "Ball Bearings", "BRG"
            if "valve" in text:
                return "Valves", "Ball Valves", "VLV"
            if "pipe" in text:
                return "Pipes", "Carbon Steel Pipes", "PIP"

        return best_category, best_subcategory, best_abbrev

_classifier_instance = None

def get_classifier() -> MaterialClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = MaterialClassifier()
    return _classifier_instance

def classify_material(normalized_description: str, material_type: str = "") -> Tuple[str, str, str]:
    return get_classifier().classify(normalized_description, material_type)
