"""Tests for app/structural_parser.py — pipeline integration and template proximity extraction."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.db import upsert_clinic, upsert_template, get_clinic_by_name, get_all_clinics, get_all_templates_with_names
from app.db_migrations import run_migrations
from app.output import write_json_atomic
from app.structural_parser import OutputWriter, process_input_json, DEFAULT_PROXIMITY_THRESHOLD

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


class TestOutputWriter:
    def test_preprocessed_raw_uses_same_structured_output_name(self, temp_output_dir: Path):
        writer = OutputWriter()
        base = "receipt-001_12345"
        regular_raw = temp_output_dir / f"{base}-raw_data.json"
        preprocessed_raw = temp_output_dir / f"{base}-raw_data.preprocessed.json"

        writer.write(temp_output_dir, regular_raw, {"source": "regular"})
        writer.write(temp_output_dir, preprocessed_raw, {"source": "preprocessed"})

        outputs = list(temp_output_dir.glob("*-structured_data.json"))
        assert outputs == [temp_output_dir / f"{base}-structured_data.json"]
        assert json.loads(outputs[0].read_text(encoding="utf-8")) == {"source": "preprocessed"}

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
        """DEFAULT_PROXIMITY_THRESHOLD が 50.0 であること"""
        assert DEFAULT_PROXIMITY_THRESHOLD == 50.0


class TestTemplateCoordBasis:
    """Issue #40: coord_basis ('date' / 'topmost') による前方補正の分岐検証。"""

    @staticmethod
    def _set_coord_basis(temp_db: Path, template_id: str, basis: str) -> None:
        """templates の coord_basis を更新する。"""
        from app.db import get_db_connection

        with get_db_connection(temp_db) as conn:
            conn.execute(
                "UPDATE templates SET coord_basis = ? WHERE id = ?",
                (basis, template_id),
            )

    def test_template_based_extraction_skipped_when_date_basis(self, temp_output_dir: Path, temp_db: Path):
        """coord_basis='date' の template では座標によるフィールド上書きがスキップされる。"""
        from app.db import get_or_create_clinic, upsert_template

        clinic_id = get_or_create_clinic(temp_db, "あおばクリニック")
        template_id = str(uuid.uuid4())
        upsert_template(
            temp_db,
            template_id,
            clinic_id,
            version=1,
            coords_corrections={
                "amount": [[400, 300], [480, 300], [480, 340], [400, 340]],
            },
        )
        # #39 移行済みを模擬
        self._set_coord_basis(temp_db, template_id, "date")

        raw_path = temp_output_dir / "receipt-001.json"
        # date 基準でも量のモック: 呼ばれたら 8888 を返す。date 基準なら呼ばれないはず。
        with patch(
            "app.structural_parser.search_fields_by_proximity",
            return_value={"amount": "8888"},
        ) as mock_proximity:
            result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # 座標上書きは実行されない（search_fields_by_proximity が呼ばれない）
        mock_proximity.assert_not_called()
        # amount はテキスト抽出（mock）結果の 3800 のまま（上書き 8888 が混入しない）
        assert result["amount"] == 3800

    def test_template_based_extraction_works_for_topmost_basis(
        self,
        temp_output_dir: Path,
        temp_db: Path,
        seed_clinic_with_template: str,
    ):
        """coord_basis='topmost' の template では従来どおり座標上書きが動作する。"""
        from app.db import get_latest_template_by_clinic

        template = get_latest_template_by_clinic(temp_db, seed_clinic_with_template)
        assert template is not None
        self._set_coord_basis(temp_db, template["id"], "topmost")

        raw_path = temp_output_dir / "receipt-001.json"
        with patch(
            "app.structural_parser.search_fields_by_proximity",
            return_value={"amount": "8888"},
        ) as mock_proximity:
            result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # topmost では座標上書きが実行される
        mock_proximity.assert_called_once()
        # 戻り値 8888 で amount が上書きされる
        assert result["amount"] == 8888

    def test_date_basis_still_fixes_clinic_name(self, temp_output_dir: Path, temp_db: Path):
        """coord_basis='date' でも、clinic 名の正しい名への上書き（③）は維持される。"""
        from app.db import get_or_create_clinic, upsert_template

        # ABCクリニック + date 基準 template を作成（#39 移行済みを模擬）
        clinic_id = get_or_create_clinic(temp_db, "ABCクリニック")
        template_id = str(uuid.uuid4())
        upsert_template(
            temp_db,
            template_id,
            clinic_id,
            version=1,
            coords_corrections={
                "amount": [[400, 300], [480, 300], [480, 340], [400, 340]],
            },
        )
        self._set_coord_basis(temp_db, template_id, "date")

        # 文字欠け（"BCクリニック"）で類似度マッチを誘発。座標は ABC template と同じレイアウト
        modified_ocr = [
            {"text": "山田 太郎", "confidence": 0.95, "box": [[50, 100], [200, 100], [200, 140], [50, 140]]},
            {"text": "BCクリニック", "confidence": 0.85, "box": [[50, 160], [300, 160], [300, 200], [50, 200]]},
            {"text": "3,800円", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
            {"text": "2026/01/15", "confidence": 0.90, "box": [[50, 50], [200, 50], [200, 80], [50, 80]]},
        ]
        raw_path = temp_output_dir / "clinic-fix.json"
        write_json_atomic(raw_path, modified_ocr)

        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # 座標上書きはスキップされ、テキスト抽出（mock）の値のまま
        assert result["amount"] == 3800
        # clinic 名の正しい名への上書き（③）は date 基準でも従来どおり動作
        assert result["clinic"] == "ABCクリニック"


class TestApplyTemplateMultiBox:
    """Tests for template-based multi-box proximity extraction (Reverse direction)."""

    MULTI_BOX_COORDS = {
        "name": [
            [[67, 126], [205, 130], [203, 198], [65, 194]],
            [[255, 126], [379, 135], [374, 209], [250, 200]],
        ],
    }

    @pytest.fixture
    def seed_multibox_template(self, temp_db: Path) -> str:
        """Insert a clinic with a multi-box name template. Returns clinic_id."""
        from app.db import get_or_create_clinic

        clinic_id = get_or_create_clinic(temp_db, "あおばクリニック")
        template_id = str(uuid.uuid4())
        upsert_template(
            temp_db,
            template_id,
            clinic_id,
            version=1,
            coords_corrections=self.MULTI_BOX_COORDS,
        )
        return clinic_id

    def test_apply_template_multi_box(
        self,
        temp_output_dir: Path,
        temp_db: Path,
        seed_multibox_template: str,
    ):
        """マルチboxテンプレート → 連結テキストで上書きされる"""
        raw_path = temp_output_dir / "receipt-001.json"

        # Split-name OCR entries
        split_ocr = [
            {"text": "山田", "confidence": 0.99, "box": [[67, 126], [205, 130], [203, 198], [65, 194]]},
            {"text": "太郎様", "confidence": 0.91, "box": [[255, 126], [379, 135], [374, 209], [250, 200]]},
            {"text": "あおばクリニック", "confidence": 0.92, "box": [[50, 160], [300, 160], [300, 200], [50, 200]]},
        ]
        write_json_atomic(raw_path, split_ocr)

        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # MockLLMClient extracts name from full text: "山田 太郎"
        # Template multi-box proximity should override with merged text "山田太郎"
        assert result["name"] == "山田太郎"  # "様" removed by rstrip

    def test_apply_template_multi_box_single_unchanged(
        self,
        temp_output_dir: Path,
        temp_db: Path,
        seed_clinic_with_template: str,
    ):
        """単一boxテンプレート → 従来通り動作"""
        raw_path = temp_output_dir / "receipt-001.json"
        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        assert result["amount"] == 3800  # not overridden (amount not in seed template)
        assert result["clinic"] == "あおばクリニック"

    def test_apply_template_no_template(
        self,
        temp_output_dir: Path,
        temp_db: Path,
    ):
        """テンプレートなし → 変更なし"""
        raw_path = temp_output_dir / "receipt-001.json"
        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        assert result["name"] == "山田 太郎"
        assert result["amount"] == 3800


# ──────────────────────────────────────────
# ハイブリッドマッチング（問題点1）のテスト
# ──────────────────────────────────────────


class TestHybridTemplateMatching:
    """Test hybrid fallback template matching (text similarity + layout)."""

    @pytest.fixture
    def seed_abc_clinic_with_template(self, temp_db: Path) -> str:
        """ABCクリニック + テンプレートをDBに登録"""
        from app.db import get_or_create_clinic

        clinic_id = get_or_create_clinic(temp_db, "ABCクリニック")
        upsert_template(
            temp_db,
            str(uuid.uuid4()),
            clinic_id,
            version=1,
            coords_corrections={
                "amount": [[400, 300], [480, 300], [480, 340], [400, 340]],
                "date": [[50, 50], [200, 50], [200, 80], [50, 80]],
            },
        )
        return clinic_id

    def test_hybrid_exact_match_first(
        self,
        temp_output_dir: Path,
        temp_db: Path,
        seed_clinic_with_template: str,
    ):
        """完全一致 → Step1 でテンプレートが適用される（後方互換性）"""
        raw_path = temp_output_dir / "receipt-001.json"
        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # テンプレートの amount 座標に一致する「3,800」で上書きされる
        assert result["amount"] == 3800
        # clinic 名はそのまま
        assert result["clinic"] == "あおばクリニック"

    def test_hybrid_text_similarity_fallback(
        self,
        temp_output_dir: Path,
        temp_db: Path,
        seed_abc_clinic_with_template: str,
    ):
        """文字欠け（"BC" → "ABC"） → Step2 テキスト類似度でマッチ"""
        # クリニック名が "BCクリニック" のOCRエントリ（ABCクリニックの文字欠け想定）
        modified_ocr = [
            {"text": "山田 太郎", "confidence": 0.95, "box": [[50, 100], [200, 100], [200, 140], [50, 140]]},
            {"text": "BCクリニック", "confidence": 0.85, "box": [[50, 160], [300, 160], [300, 200], [50, 200]]},
            {"text": "3,800円", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
            {"text": "2026/01/15", "confidence": 0.90, "box": [[50, 50], [200, 50], [200, 80], [50, 80]]},
        ]
        raw_path = temp_output_dir / "similarity-test.json"
        write_json_atomic(raw_path, modified_ocr)

        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # テンプレート座標で amount が補正される
        assert result["amount"] == 3800
        # clinic 名が正しい "ABCクリニック" に上書きされる
        assert result["clinic"] == "ABCクリニック"
        # 元の "BCクリニック" が clinic として新規作成されていないこと
        clinic = get_clinic_by_name(temp_db, "BCクリニック")
        assert clinic is None

    def test_hybrid_layout_fallback(
        self,
        temp_output_dir: Path,
        temp_db: Path,
        seed_abc_clinic_with_template: str,
    ):
        """クリニック名が全く異なる → Step3 座標レイアウトでマッチ"""
        # クリニック名に「医院」を含める（MockLLMClient が clinic として認識するため）
        # 座標は ABCクリニックのテンプレートと同じレイアウト
        modified_ocr = [
            {"text": "山田 太郎", "confidence": 0.95, "box": [[50, 100], [200, 100], [200, 140], [50, 140]]},
            {"text": "全然違う医院", "confidence": 0.92, "box": [[50, 160], [300, 160], [300, 200], [50, 200]]},
            {"text": "3,800円", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
            {"text": "2026/01/15", "confidence": 0.90, "box": [[50, 50], [200, 50], [200, 80], [50, 80]]},
        ]
        raw_path = temp_output_dir / "layout-test.json"
        write_json_atomic(raw_path, modified_ocr)

        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # テンプレート座標で amount が補正される
        assert result["amount"] == 3800
        # clinic 名が "ABCクリニック" に上書きされる（レイアウトマッチによる）
        assert result["clinic"] == "ABCクリニック"

    def test_hybrid_all_fallback_no_match(
        self,
        temp_output_dir: Path,
        temp_db: Path,
    ):
        """全マッチ失敗 → 従来通り新規クリニックとして処理"""
        # テンプレートなしのOCRエントリ
        no_match_ocr = [
            {"text": "商品名", "confidence": 0.95, "box": [[50, 100], [200, 100], [200, 140], [50, 140]]},
            {"text": "3,800円", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
        ]
        raw_path = temp_output_dir / "no-match.json"
        write_json_atomic(raw_path, no_match_ocr)

        result = process_input_json(raw_path, model="mock", output_dir=temp_output_dir, db_path=temp_db)

        assert result is not None
        # clinic は None（OCRにクリニック名がない）
        assert result["clinic"] is None
        # エラーが発生しないこと
        assert result["amount"] == 3800
