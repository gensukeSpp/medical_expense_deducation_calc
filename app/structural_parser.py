"""Structural parser: converts OCR JSON -> structured data using LLM extractor and normalization."""

from __future__ import annotations
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from app.input import read_json
from app.llm_extractor import get_llm_client
from app.normalization import normalize_extracted
from app.output import write_json_atomic
from app.error_logging import append_error
from app.db import insert_receipt, get_or_create_clinic


def process_input_json(
    input_path: Path | str,
    model: str = "mock",
    output_dir: Path | str = "output_json",
    db_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Process an OCR JSON file to extract and normalize structured fields.

    Args:
        input_path: Path to the input OCR JSON file.
        model: The LLM model name or 'mock' for local heuristics.
        output_dir: The directory where the structured JSON output will be saved.
        db_path: Optional path to SQLite database for persistence.

    Returns:
        The normalized structured data dictionary, or None if processing failed.
    """
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

    # output to JSON file
    try:
        out_name = f"{input_path.stem}-structured_data.json"
        out_path = output_dir / out_name
        write_json_atomic(out_path, structured)
    except Exception as e:
        append_error(output_dir, str(input_path), str(e), "write_output", {"structured": structured})
        return None

    # DB persistence
    if db_path:
        try:
            """
            競合状態（レースコンディション）と外部キー制約違反のリスクがあります。\n\n
            現在の実装では、get_clinic_by_name でクリニックの存在を確認した後に upsert_clinic を呼び出す「Check-then-Act」パターンを採用しています。\n
            マルチプロセスや並列実行環境において、同じクリニック名のデータがほぼ同時に処理された場合、既存のクリニックIDが新しいUUIDに更新されてしまい、既にそのクリニックIDを参照している receipts レコードが存在すると、外部キー制約違反（IntegrityError）が発生して処理がクラッシュします。\n\n
            新しく追加した get_or_create_clinic を使用して、アトミックにクリニックIDを取得・作成するように修正してください。
            """
            clinic_name = structured.get("clinic")
            clinic_id = None
            if clinic_name:
                clinic_name = str(clinic_name).strip()
                if clinic_name:
                    # check if clinic exists, otherwise create it safely
                    clinic_id = get_or_create_clinic(db_path, clinic_name)

            receipt_id = str(uuid.uuid4())
            insert_receipt(
                db_path=db_path,
                receipt_id=receipt_id,
                source_path=str(input_path),
                ocr_json=ocr_json,
                normalized_json=structured,
                clinic_id=clinic_id,
            )
        except Exception as e:
            # If DB insert fails, log error but continue processing to maintain robustness
            append_error(
                output_dir,
                str(input_path),
                f"DB persistence failed: {e}",
                "db_persistence",
                {"structured": structured},
            )

    return structured
