import re
from typing import Dict, Any
from app.config import get_normalization_dict
from app.utils.text_utils import clean_text, standardize_separators

class TextNormalizer:
    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            config = get_normalization_dict()
        self.abbreviations = config.get("abbreviations", {})
        self.units = config.get("units", {})
        self._build_regex()

    def _build_regex(self):
        # Sort abbreviations by length descending to match longer phrases first (e.g., STAINLESS STEEL before SS)
        sorted_abbr = sorted(self.abbreviations.keys(), key=lambda x: len(x), reverse=True)
        # Escape keys for regex
        escaped_abbr = [re.escape(k) for k in sorted_abbr]
        # Match whole words or tokens bounded by word boundaries or punctuation
        if escaped_abbr:
            pattern_str = r'(?<!\w)(' + '|'.join(escaped_abbr) + r')(?!\w)'
            self.abbr_pattern = re.compile(pattern_str, re.IGNORECASE)
        else:
            self.abbr_pattern = None

    def normalize(self, text: str) -> str:
        """
        Cleans text, normalizes abbreviations, units, dimension separators,
        and produces a canonical uppercase string representation.
        """
        if not text:
            return ""

        # Initial clean
        text = clean_text(text)

        # Standardize dimension multiplier symbols (X, x, ×, *, by)
        text = standardize_separators(text)

        # Expand abbreviations
        if self.abbr_pattern:
            def replace_abbr(match):
                word = match.group(0).upper()
                # Find matching key ignoring case
                for k, v in self.abbreviations.items():
                    if k.upper() == word:
                        return v
                return match.group(0)

            text = self.abbr_pattern.sub(replace_abbr, text)

        # Standardize units
        # e.g., 50MM -> 50 mm, 16 MM -> 16 mm, 2" -> 2 inch
        text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:"|\'\'|inch\b|in\.?\b|inches\b)', r'\1 inch ', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:mm\b|m\.m\.\b|millimeter\b|millimetre\b)', r'\1 mm ', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:kg\b|kgs\b|kilogram\b)', r'\1 kg ', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:mtr\b|mtrs\b|meter\b|metre\b|m\b)', r'\1 meter ', text, flags=re.IGNORECASE)
        
        # Standardize metric fastener dimensions (e.g. 16 mm x 50 mm, M16-50, M16 x 50 -> M16 X 50 mm)
        text = re.sub(r'\b(\d+)\s*mm\s*[xX]\s*(\d+(?:\.\d+)?)(?:\s*mm)?\b', r'M\1 X \2 mm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bM(\d+)\s*[\-xX]\s*(\d+(?:\.\d+)?)(?:\s*mm)?\b', r'M\1 X \2 mm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bM(\d+)\s+X\s+(\d+(?:\.\d+)?)(?:\s*mm)?\b', r'M\1 X \2 mm', text, flags=re.IGNORECASE)

        # Clean multiple spaces and strip punctuation at boundaries
        text = clean_text(text)
        return text

# Global singleton instance for performance
_normalizer_instance = None

def get_normalizer() -> TextNormalizer:
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = TextNormalizer()
    return _normalizer_instance

def normalize_text(text: str) -> str:
    return get_normalizer().normalize(text)
