"""Utilities for logging errors to a JSON Lines file."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict


def append_error(output_dir: Path, file: str, error: str, step: str, context: Dict[str, Any] | None = None) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "errors.log"
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "file": file,
        "error": error,
        "step": step,
        "context": context or {},
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
