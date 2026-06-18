"""Structural parser: converts OCR JSON -> structured data using LLM extractor and normalization."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Optional

from app.llm_extractor import MockLLMClient, RealLLMClient
from app.normalization import parse_amount, parse_date
from app.error_logging import append_error


def process_input_json(input_path: Path | str, model: str = "mock", output_dir: Path | str = "output_json") -> Optional[Dict[str, Any]]:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            ocr_json = json.load(f)
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "read_input", {})
        return None

    try:
        if model == "mock":
            client = MockLLMClient()
        else:
            client = RealLLMClient(model)
        extracted = client.extract_fields(ocr_json)
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "llm_extract", {})
        extracted = {"name": None, "clinic": None, "amount": None, "date": None}

    # normalization
    try:
        amount = extracted.get("amount")
        # If amount already numeric, keep. If string, try to parse.
        if isinstance(amount, str):
            amount = parse_amount(amount)
        elif amount is None:
            # try to infer from OCR text_lines
            lines = ocr_json.get("text_lines") or [w.get("text") for w in ocr_json.get("words", []) if w.get("text")]
            # naive search
            for ln in lines:
                if '円' in ln or '万' in ln:
                    amount = parse_amount(ln)
                    if amount:
                        break
        # date
        date = extracted.get("date")
        if isinstance(date, str):
            norm_date = parse_date(date)
            date = norm_date
        elif date is None:
            lines = ocr_json.get("text_lines") or [w.get("text") for w in ocr_json.get("words", []) if w.get("text")]
            for ln in lines:
                if any(ch in ln for ch in ['年', '/', '-']):
                    d = parse_date(ln)
                    if d:
                        date = d
                        break
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "normalization", {"extracted": extracted})
        # keep extracted as-is
        amount = extracted.get("amount")
        date = extracted.get("date")

    structured = {
        "name": extracted.get("name"),
        "clinic": extracted.get("clinic"),
        "amount": amount,
        "date": date,
    }

    # output
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"{input_path.stem}-structured_data.json"
        out_path = output_dir / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "write_output", {"structured": structured})
        return None

    return structured
