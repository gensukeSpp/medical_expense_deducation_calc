"""Utilities for logging errors to a JSON Lines file."""

from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict


def append_error(output_dir: Path, file: str, error: str, step: str, context: Dict[str, Any] | None = None) -> None:
    """Append an error entry to the errors.log file in JSON Lines format.

    Args:
        output_dir: The directory where the error log file is located.
        file: The path or name of the file being processed when the error occurred.
        error: The error message or exception string.
        step: The processing step where the error occurred (e.g., 'read_input').
        context: Optional dictionary containing additional context about the error.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "errors.log"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "file": file,
        "error": error,
        "step": step,
        "context": context or {},
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
