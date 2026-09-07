"""
Compatibility wrapper for app/app.py forwarding to app/main.py
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.main import main

if __name__ == "__main__":
    main()
