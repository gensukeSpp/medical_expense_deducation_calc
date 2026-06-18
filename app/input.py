"""Input handling: reads OCR JSON from file."""

from pathlib import Path
import json
from typing import Dict, Any


def read_json(path: Path) -> Dict[str, Any]:
    """Read OCR JSON from file path. Returns parsed dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
