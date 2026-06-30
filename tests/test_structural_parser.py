"""Tests for app/structural_parser.py — pipeline integration and template proximity extraction."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.db import upsert_clinic, upsert_template
from app.db_migrations import run_migrations
from app.output import write_json_atomic
from app.structural_parser import process_input_json, DEFAULT_PROXIMITY_THRESHOLD

SCHEMA_PATH = Path("docs/schema.sql")

SAMPLE_OCR_ENTRIES = [
    {"text": "山田 太郎", "confidence": 0.95, "box": [[50, 100], [200, 100], [200, 140], [50, 140]]},
    {"text": "あおばクリニック", "confidence": 0.92, "box": [[50, 160], [300, 160], [300, 200], [50, 200]]},
    {"text": "3,800円", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
    {"text": "2026/01/15", "confidence": 0.90, "box": [[50, 50], [200, 50], [200, 80], [50, 80]]},
]


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create temp output_json dir and write a mock raw_data.json."""
    out_dir = tmp_path / "output_json"
    out_dir.mkdir()
    write_json_atomic(out_dir / "receipt-001.json", SAMPLE_OCR_ENTRIES)
    return out_dir


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a fresh schema-applied temp DB."""
    db_file = tmp_path / "test_db.sqlite3"
    run_migrations(db_file, SCHEMA_PATH)
    return db_file


@pytest.fixture
def seed_clinic_with_template(temp_db: Path) -> str:
    """Insert a clinic with a coordinate template into DB. Returns clinic_id."""
    clinic_id = str(uuid.uuid4())
    template_id = str(uuid.uuid4())
    upsert_clinic(temp_db, clinic_id, "あおばクリニック")
    upsert_template(
        temp_db,
        template_id,
        clinic_id,
        version=1,
        coords_corrections={
            "amount": [[400, 300], [480, 300], [480, 340], [400, 340]],
            "date": [[50, 50], [200, 50], [200, 80], [50, 80]],
        },
    )
    return clinic_id


class TestProcessInputJson:
    """Test process_input_json basic pipeline."""

    def test_process_input_json_creates_structured_json(self, temp_output_dir: Path):
        """raw_data.json → structured_data.json が生成される"""
        raw_path = temp_output_dir / "receipt-001.json"
        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir)

        assert result is not None
        assert "name" in result
        assert "clinic" in result
        assert "amount" in result
        assert "date" in result

        # structured_data.json が生成されている
        structured_path = temp_output_dir / "receipt-001-structured_data.json"
        assert structured_path.exists()
        with open(structured_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["clinic"] == "あおばクリニック"

    def test_template_based_extraction_override(
        self,
        temp_output_dir: Path,
        temp_db: Path,
        seed_clinic_with_template: str,
    ):
        """テンプレート座標に一致する場合、MockLLMClient の抽出結果が上書きされる"""
        raw_path = temp_output_dir / "receipt-001.json"

        # 「山田 太郎」→「山田 花子」に上書きされるよう OCR エントリを変更
        # 名前の座標位置（center: 125, 120）に近い OCR エントリを用意
        modified_ocr = [
            {"text": "山田 花子", "confidence": 0.95, "box": [[50, 100], [200, 100], [200, 140], [50, 140]]},
            {"text": "あおばクリニック", "confidence": 0.92, "box": [[50, 160], [300, 160], [300, 200], [50, 200]]},
            {"text": "9,999円", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
            {"text": "2026/06/29", "confidence": 0.90, "box": [[50, 50], [200, 50], [200, 80], [50, 80]]},
        ]
        write_json_atomic(raw_path, modified_ocr)

        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # テンプレートの amount 座標に一致する「9,999」で amount が上書きされる
        assert result["amount"] == 9999  # normalize_extracted で整数化
        # テンプレートの date 座標に一致する「2026/06/29」で date が上書きされる
        assert result["date"] == "2026-06-29"

    def test_template_no_match_falls_back(
        self,
        temp_output_dir: Path,
        temp_db: Path,
    ):
        """テンプレート座標が OCR 結果とマッチしない場合、通常抽出結果が維持される"""
        raw_path = temp_output_dir / "receipt-001.json"

        # マッチしないテンプレート座標を DB に作成
        clinic_id = str(uuid.uuid4())
        template_id = str(uuid.uuid4())
        upsert_clinic(temp_db, clinic_id, "あおばクリニック")
        upsert_template(
            temp_db,
            template_id,
            clinic_id,
            version=1,
            coords_corrections={
                "amount": [[0, 9999], [10, 9999], [10, 10010], [0, 10010]],  # 領収書外の座標
            },
        )

        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # テンプレートマッチなし → MockLLMClient の通常抽出結果
        assert result["amount"] == 3800
        assert result["clinic"] == "あおばクリニック"

    def test_template_without_db_skips(self, temp_output_dir: Path):
        """db_path=None の場合、テンプレート連携がスキップされる"""
        raw_path = temp_output_dir / "receipt-001.json"
        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=None)

        assert result is not None
        assert result["clinic"] == "あおばクリニック"
        assert result["amount"] == 3800

    def test_template_without_clinic_skips(self, temp_output_dir: Path, temp_db: Path):
        """clinic が抽出されなかった場合、テンプレート連携がスキップされる"""
        # clinic なしの OCR エントリ
        no_clinic_ocr = [
            {"text": "商品名", "confidence": 0.95, "box": [[50, 100], [200, 100], [200, 140], [50, 140]]},
            {"text": "3,800円", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
        ]
        raw_path = temp_output_dir / "no-clinic.json"
        write_json_atomic(raw_path, no_clinic_ocr)

        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        assert result["clinic"] is None  # clinic なし
        # エラーが発生しないこと
        assert result["amount"] == 3800

    def test_proximity_threshold_default(self):
        """DEFAULT_PROXIMITY_THRESHOLD が 20.0 であること"""
        assert DEFAULT_PROXIMITY_THRESHOLD == 20.0