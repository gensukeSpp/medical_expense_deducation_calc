"""Tests for app/services/ocr_coordinate_service.py — multi-box substring fallback."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.db import upsert_clinic, insert_receipt
from app.db_migrations import run_migrations
from app.services.ocr_coordinate_service import OCRCoordinateService

SCHEMA_PATH = Path("docs/schema.sql")


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a fresh schema-applied temp DB."""
    db_file = tmp_path / "test_db.sqlite3"
    run_migrations(db_file, SCHEMA_PATH)
    return db_file


@pytest.fixture
def seed_split_name_receipt(temp_db: Path, tmp_path: Path):
    """Insert a clinic and receipt with split-name OCR entries."""
    clinic_id = str(uuid.uuid4())
    receipt_id = str(uuid.uuid4())
    upsert_clinic(temp_db, clinic_id, "テストクリニック")

    ocr_entries = [
        {"text": "山田", "confidence": 0.99, "box": [[67, 126], [205, 130], [203, 198], [65, 194]]},
        {"text": "太郎様", "confidence": 0.91, "box": [[255, 126], [379, 135], [374, 209], [250, 200]]},
        {"text": "あおばクリニック", "confidence": 0.92, "box": [[50, 160], [300, 160], [300, 200], [50, 200]]},
        {"text": "3,800", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
    ]
    insert_receipt(
        temp_db,
        receipt_id=receipt_id,
        source_path=str(tmp_path / "receipt.json"),
        ocr_json=ocr_entries,
        normalized_json={"name": "", "clinic": "テストクリニック", "amount": 3800},
        clinic_id=clinic_id,
    )
    return {"clinic_id": clinic_id, "receipt_id": receipt_id}


class TestProcessFeedbackMultiBoxFallback:
    """Tests for Forward direction substring fallback in process_feedback."""

    def test_process_feedback_multi_box_fallback(self, temp_db: Path, seed_split_name_receipt: dict, tmp_path: Path):
        """テキスト検索失敗 → サブストリングフォールバック → マルチbox保存"""
        service = OCRCoordinateService(db_path=temp_db, output_dir=tmp_path)
        clinic_id = seed_split_name_receipt["clinic_id"]
        receipt_id = seed_split_name_receipt["receipt_id"]

        result = service.process_feedback(
            file_stem="receipt",
            file_path=tmp_path / "receipt-structured_data.json",
            old_data={"name": "", "clinic": "テストクリニック", "amount": 3800},
            updates={"name": "山田太郎"},
            receipt_id=receipt_id,
            clinic_id=clinic_id,
        )

        assert result is not None
        assert "name" in result["updated_fields"], "name should be in updated_fields"
        assert result["updated_fields"] == ["name"]

    def test_process_feedback_no_fallback_single_ok(
        self, temp_db: Path, seed_split_name_receipt: dict, tmp_path: Path
    ):
        """テキスト検索成功 → フォールバック不要"""
        service = OCRCoordinateService(db_path=temp_db, output_dir=tmp_path)
        clinic_id = seed_split_name_receipt["clinic_id"]
        receipt_id = seed_split_name_receipt["receipt_id"]

        result = service.process_feedback(
            file_stem="receipt",
            file_path=tmp_path / "receipt-structured_data.json",
            old_data={"name": "", "clinic": "テストクリニック", "amount": 3800},
            updates={"amount": "3800"},  # exact match exists in OCR
            receipt_id=receipt_id,
            clinic_id=clinic_id,
        )

        assert result is not None
        assert "amount" in result["updated_fields"], "amount should be found via text search"

    def test_process_feedback_fallback_low_similarity(self, temp_db: Path, tmp_path: Path):
        """連結後の類似度不足 → フォールバック reject"""
        # Create receipt with OCR entries that don't form a valid multi-box match
        clinic_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())
        upsert_clinic(temp_db, clinic_id, "テストクリニック2")

        ocr_entries = [
            {"text": "東京", "confidence": 0.99, "box": [[50, 100], [150, 100], [150, 150], [50, 150]]},
            {"text": "特許", "confidence": 0.91, "box": [[200, 100], [300, 100], [300, 150], [200, 150]]},
            {"text": "許可局", "confidence": 0.88, "box": [[350, 100], [450, 100], [450, 150], [350, 150]]},
        ]
        insert_receipt(
            temp_db,
            receipt_id=receipt_id,
            source_path=str(tmp_path / "receipt2.json"),
            ocr_json=ocr_entries,
            normalized_json={"name": "", "clinic": "テストクリニック2", "amount": 0},
            clinic_id=clinic_id,
        )

        service = OCRCoordinateService(db_path=temp_db, output_dir=tmp_path)
        result = service.process_feedback(
            file_stem="receipt2",
            file_path=tmp_path / "receipt2-structured_data.json",
            old_data={"name": "", "clinic": "テストクリニック2", "amount": 0},
            updates={"name": "山田太郎"},  # "東京特許許可局" != "山田太郎" → similarity low
            receipt_id=receipt_id,
            clinic_id=clinic_id,
        )

        # Fallback should reject due to low similarity
        assert result is not None
        assert "name" not in result["updated_fields"]

    def test_process_feedback_multi_line_reject(self, temp_db: Path, tmp_path: Path):
        """別ラインのサブストリング → reject"""
        clinic_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())
        upsert_clinic(temp_db, clinic_id, "テストクリニック3")

        # "山田" on line 1, "太郎" on a different Y line
        ocr_entries = [
            {"text": "山田", "confidence": 0.99, "box": [[67, 126], [205, 130], [203, 198], [65, 194]]},
            # Different Y range (line below)
            {"text": "太郎", "confidence": 0.91, "box": [[67, 326], [205, 330], [203, 398], [65, 394]]},
            {"text": "あおばクリニック", "confidence": 0.92, "box": [[50, 460], [300, 460], [300, 500], [50, 500]]},
        ]
        insert_receipt(
            temp_db,
            receipt_id=receipt_id,
            source_path=str(tmp_path / "receipt3.json"),
            ocr_json=ocr_entries,
            normalized_json={"name": "", "clinic": "テストクリニック3", "amount": 0},
            clinic_id=clinic_id,
        )

        service = OCRCoordinateService(db_path=temp_db, output_dir=tmp_path)
        result = service.process_feedback(
            file_stem="receipt3",
            file_path=tmp_path / "receipt3-structured_data.json",
            old_data={"name": "", "clinic": "テストクリニック3", "amount": 0},
            updates={"name": "山田太郎"},
            receipt_id=receipt_id,
            clinic_id=clinic_id,
        )

        # "山田" and "太郎" are on different Y lines with 200px gap
        # The _find_multi_boxes_by_substring should reject across lines
        assert result is not None
        assert "name" not in result["updated_fields"]
