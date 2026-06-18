"""Output helper utilities for writing OCR JSON results safely."""

from pathlib import Path
import json
import tempfile
import os
import time


def write_json(path: Path, obj: dict):
    """Write JSON to file, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_json_atomic(path: Path, data, retries: int = 3, delay: float = 0.1) -> None:
    """Write JSON atomically: write to a temp file then rename.

    Args:
        path: target path
        data: JSON-serializable object
        retries: number of write attempts on IOError
        delay: delay between retries
    """
    path = Path(path)
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = path.parent
    attempt = 0
    while True:
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(tmp_dir))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                # atomic rename
                os.replace(tmp_path, str(path))
                return
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        except IOError:
            attempt += 1
            if attempt >= retries:
                raise
            time.sleep(delay)
