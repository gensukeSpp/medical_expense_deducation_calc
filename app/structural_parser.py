"""Structural parser: converts OCR JSON -> structured data using LLM extractor and normalization."""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional

from app.input import read_json
from app.llm_extractor import get_llm_client
from app.normalization import normalize_extracted
from app.output import write_json
from app.error_logging import append_error


def process_input_json(
    input_path: Path | str, model: str = "mock", output_dir: Path | str = "output_json"
) -> Optional[Dict[str, Any]]:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    try:
        ocr_json = read_json(input_path)
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "read_input", {})
        return None

    try:
        client = get_llm_client(model)
        extracted = client.extract_fields(ocr_json)
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "llm_extract", {})
        extracted = {"name": None, "clinic": None, "amount": None, "date": None}

    # normalization
    try:
        structured = normalize_extracted(extracted, ocr_json)
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "normalization", {"extracted": extracted})
        # keep extracted as-is
        structured = extracted

    # output
    try:
        out_name = f"{input_path.stem}-structured_data.json"
        out_path = output_dir / out_name
        write_json(out_path, structured)
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "write_output", {"structured": structured})
        return None

    return structured
