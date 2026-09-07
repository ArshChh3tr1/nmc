import re

def clean_text(text: str) -> str:
    """Removes irregular whitespace, control characters, and standardizes casing."""
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def standardize_separators(text: str) -> str:
    """Standardizes dimension cross signs like ×, *, by, X into 'X' surrounded by spaces."""
    if not text:
        return ""
    # Standardize dimension multiplier symbols
    text = re.sub(r'(?<=\d)\s*(?:[xX×\*]|by)\s*(?=\d)', ' X ', text)
    # Standardize hyphens between metric threads and lengths e.g. M16-50 -> M16 X 50
    text = re.sub(r'\b(M\d+)\s*[-/]\s*(\d+)\b', r'\1 X \2', text, flags=re.IGNORECASE)
    return text

def clean_dimension_token(token: str) -> str:
    if not token:
        return ""
    token = token.strip().upper()
    token = token.replace('"', 'INCH').replace("''", 'INCH')
    return token
