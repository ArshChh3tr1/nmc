import re
import json
from typing import Dict, Any, Optional
from app.services.normalization.normalizer import get_normalizer

class AttributeExtractor:
    def __init__(self):
        self.normalizer = get_normalizer()

    def extract(self, raw_description: str, normalized_description: Optional[str] = None, uom_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts material, type, dimensions dict, specification, and uom from description.
        No LLM calls; pure regex and deterministic lookup.
        """
        if not normalized_description:
            normalized_description = self.normalizer.normalize(raw_description or "")

        norm_upper = normalized_description.upper()

        material = self._extract_material(norm_upper)
        mat_type = self._extract_type(norm_upper)
        dimensions = self._extract_dimensions(norm_upper, mat_type)
        specification = self._extract_specification(norm_upper)
        uom = self._extract_uom(norm_upper, uom_hint)

        return {
            "material": material,
            "type": mat_type,
            "dimensions": dimensions,
            "dimensions_json": json.dumps(dimensions, sort_keys=True),
            "specification": specification,
            "uom": uom
        }

    def _extract_material(self, text: str) -> str:
        # Check specific grades first
        if re.search(r'\b(SS\s*316L?|STAINLESS STEEL\s*316L?)\b', text):
            return "Stainless Steel 316"
        if re.search(r'\b(SS\s*304L?|STAINLESS STEEL\s*304L?)\b', text):
            return "Stainless Steel 304"
        if re.search(r'\b(STAINLESS STEEL|SS|S/S|STL)\b', text):
            return "Stainless Steel"
        if re.search(r'\b(CARBON STEEL|CS|C/S|A106|A234|WPB)\b', text):
            return "Carbon Steel"
        if re.search(r'\b(MILD STEEL|MS|M/S)\b', text):
            return "Mild Steel"
        if re.search(r'\b(BRASS)\b', text):
            return "Brass"
        if re.search(r'\b(BRONZE)\b', text):
            return "Bronze"
        if re.search(r'\b(COPPER)\b', text):
            return "Copper"
        if re.search(r'\b(ALUMINIUM|ALUMINUM)\b', text):
            return "Aluminium"
        if re.search(r'\b(CAST IRON|CI)\b', text):
            return "Cast Iron"
        if re.search(r'\b(PTFE|TEFLON)\b', text):
            return "PTFE"
        if re.search(r'\b(VITON)\b', text):
            return "Viton"
        if re.search(r'\b(NBR|NITRILE)\b', text):
            return "Nitrile Rubber"
        return "Generic / Unspecified"

    def _extract_type(self, text: str) -> str:
        if re.search(r'\b(HEX(?:AGONAL)?\s*(?:HEAD\s*)?BOLT|MACHINE BOLT)\b', text):
            return "Hex Bolt"
        if re.search(r'\b(STUD(?:\s*BOLT)?)\b', text):
            return "Stud"
        if re.search(r'\b(HEX(?:AGONAL)?\s*NUT|LOCK\s*NUT|NUT)\b', text):
            return "Nut"
        if re.search(r'\b(PLAIN\s*WASHER|SPRING\s*WASHER|FLAT\s*WASHER|WASHER)\b', text):
            return "Washer"
        if re.search(r'\b(BALL\s*BEARING|DEEP\s*GROOVE\s*BALL\s*BEARING)\b', text):
            return "Ball Bearing"
        if re.search(r'\b(ROLLER\s*BEARING|TAPER\s*ROLLER\s*BEARING)\b', text):
            return "Roller Bearing"
        if re.search(r'\b(BALL\s*VALVE)\b', text):
            return "Ball Valve"
        if re.search(r'\b(GATE\s*VALVE)\b', text):
            return "Gate Valve"
        if re.search(r'\b(GLOBE\s*VALVE)\b', text):
            return "Globe Valve"
        if re.search(r'\b(PIPE|TUBING)\b', text):
            return "Pipe"
        if re.search(r'\b(CABLE\s*GLAND)\b', text):
            return "Cable Gland"
        if re.search(r'\b(POWER\s*CABLE|CONTROL\s*CABLE|CABLE)\b', text):
            return "Cable"
        if re.search(r'\b(FUSE)\b', text):
            return "Fuse"
        if re.search(r'\b(O-?RING)\b', text):
            return "O-Ring"
        if re.search(r'\b(MECHANICAL\s*SEAL)\b', text):
            return "Mechanical Seal"
        if re.search(r'\b(PRESSURE\s*GAUGE)\b', text):
            return "Pressure Gauge"
        if re.search(r'\b(TEMPERATURE\s*SENSOR|RTD|THERMOCOUPLE)\b', text):
            return "Temperature Sensor"
        if re.search(r'\b(PRESSURE\s*TRANSMITTER)\b', text):
            return "Pressure Transmitter"
        if re.search(r'\b(GASKET)\b', text):
            return "Gasket"
        if re.search(r'\b(FLANGE)\b', text):
            return "Flange"
        return "General Item"

    def _extract_dimensions(self, text: str, mat_type: str) -> Dict[str, Any]:
        dims: Dict[str, Any] = {}

        # 1. Thread and Bolt dimensions: e.g. M16 X 50, M16-50, 16mm X 50mm, M20 X 80
        # Check standard Metric thread: M<size> X <length>
        m_match = re.search(r'\bM(\d+)(?:\s*[X\-]\s*(\d+(?:\.\d+)?))?\b', text)
        if m_match:
            dia = float(m_match.group(1))
            dims["thread"] = f"M{int(dia)}"
            dims["diameter_mm"] = dia
            if m_match.group(2):
                dims["length_mm"] = float(m_match.group(2))

        # Check explicit diameter + length pattern: e.g. 16mm X 50mm or 16 mm X 50 mm
        dia_len_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:MM)?\s*X\s*(\d+(?:\.\d+)?)\s*(?:MM)?\b', text)
        if dia_len_match:
            d_val = float(dia_len_match.group(1))
            l_val = float(dia_len_match.group(2))
            if "diameter_mm" not in dims:
                dims["diameter_mm"] = d_val
                # If diameter matches metric thread range, also populate thread
                if d_val in [6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 27, 30, 36]:
                    dims["thread"] = f"M{int(d_val)}"
            if "length_mm" not in dims:
                dims["length_mm"] = l_val

        # Check explicit diameter without cross: e.g. DIA 25 MM or 25MM DIA
        if "diameter_mm" not in dims:
            dia_match = re.search(r'(?:DIA(?:METER)?\s*:?\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:MM)?\s*DIA\b)', text)
            if dia_match:
                val = dia_match.group(1) or dia_match.group(2)
                dims["diameter_mm"] = float(val)

        # Check explicit length: e.g. LENGTH 100 MM or 100MM LENGTH or L=100
        if "length_mm" not in dims:
            len_match = re.search(r'(?:LENGTH|LEN|L)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:MM)?\b', text)
            if len_match:
                dims["length_mm"] = float(len_match.group(1))

        # 2. Bearing code numbers: e.g. 6205, 6308, 6205-2RS, 6309ZZ
        brg_match = re.search(r'\b(6\d{3}|7\d{3}|3\d{4}|2\d{4})(?:-?2RS|-?ZZ|-?Z|-?RS)?\b', text)
        if brg_match:
            dims["bearing_code"] = brg_match.group(0)

        # 3. Pipe & Flange NB (Nominal Bore) & Schedule / Class
        nb_match = re.search(r'(?:NB\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:INCH|\")(?:\s*NB)?|(\d+(?:\.\d+)?)\s*MM\s*NB)', text)
        if nb_match:
            val = nb_match.group(1) or nb_match.group(2) or nb_match.group(3)
            dims["nominal_bore"] = float(val)

        sch_match = re.search(r'\bSCH(?:EDULE)?\s*[-:]?\s*(\d+[A-Z]?|STD|XS|XXS)\b', text)
        if sch_match:
            dims["schedule"] = sch_match.group(1)

        rating_match = re.search(r'(?:CLASS|RATING|#)\s*(\d+)\b|\b(\d+)\s*(?:#|LBS\b|CLASS\b)', text)
        if rating_match:
            val = rating_match.group(1) or rating_match.group(2)
            dims["pressure_class"] = int(val)

        # 4. Cable cores & cross-section: e.g. 3C X 2.5 SQMM
        cable_match = re.search(r'\b(\d+)\s*C\s*X\s*(\d+(?:\.\d+)?)\s*(?:SQMM|SQ\.MM|MM2)?\b', text)
        if cable_match:
            dims["cores"] = int(cable_match.group(1))
            dims["sqmm"] = float(cable_match.group(2))

        # 5. Pressure rating for gauges / valves (e.g. 0-10 BAR, 16 BAR)
        press_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:TO|-)\s*(\d+(?:\.\d+)?)\s*(BAR|PSI|KG/CM2)\b|\b(\d+(?:\.\d+)?)\s*(BAR|PSI|KG/CM2)\b', text)
        if press_match:
            if press_match.group(1) and press_match.group(2):
                dims["pressure_range"] = f"{press_match.group(1)}-{press_match.group(2)} {press_match.group(3)}"
            elif press_match.group(4):
                dims["pressure_rating"] = f"{press_match.group(4)} {press_match.group(5)}"

        return dims

    def _extract_specification(self, text: str) -> str:
        # Match ISO, ASTM, DIN, IS, ANSI standards
        spec_match = re.search(r'\b((?:ISO|DIN|IS|ASTM|ASME|BS|API)\s*[-:]?\s*[A-Z0-9]+(?:\s*[A-Z0-9]+)?)\b', text)
        if spec_match:
            return spec_match.group(1).strip()
        return "Standard"

    def _extract_uom(self, text: str, uom_hint: Optional[str] = None) -> str:
        if uom_hint and uom_hint.strip():
            hint_upper = uom_hint.strip().upper()
            if hint_upper in ["EA", "EACH", "NO", "NOS", "NUMBERS", "PCS", "PIECE"]:
                return "NOS"
            if hint_upper in ["M", "MTR", "MTRS", "METER", "METRE"]:
                return "MTR"
            if hint_upper in ["KG", "KGS", "KILOGRAM"]:
                return "KG"
            if hint_upper in ["SET", "SETS"]:
                return "SET"
            if hint_upper in ["PAIR", "PAIRS"]:
                return "PAIR"
            if hint_upper in ["LTR", "LITER", "LITRE"]:
                return "LTR"
            return hint_upper

        # Infer from text if any
        if re.search(r'\b(NOS|EA|PCS)\b', text):
            return "NOS"
        if re.search(r'\b(MTR|METER)\b', text):
            return "MTR"
        if re.search(r'\b(KG|KGS)\b', text):
            return "KG"
        if re.search(r'\b(SET|SETS)\b', text):
            return "SET"
        return "NOS"

_extractor_instance = None

def get_attribute_extractor() -> AttributeExtractor:
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = AttributeExtractor()
    return _extractor_instance

def extract_attributes(raw_description: str, normalized_description: Optional[str] = None, uom_hint: Optional[str] = None) -> Dict[str, Any]:
    return get_attribute_extractor().extract(raw_description, normalized_description, uom_hint)
