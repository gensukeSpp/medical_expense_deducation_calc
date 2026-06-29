# Issue #24: テスト計画

## テスト戦略

- **フレームワーク**: pytest
- **FakeOCR**: `test_watcher_integration.py` の `FakeOCR` クラスを流用（既存）
- **DB**: `tmp_path` フィクスチャで一時 SQLite DB を作成（`tests/conftest.py` のパターンを踏襲）
- **テスト用フィクスチャ**: `tests/test_structural_parser.py` に共通フィクスチャを定義

## テスト用フィクスチャ

### `tests/conftest.py` または各テストファイル内で定義

```python
@pytest.fixture
def sample_ocr_entries():
    """OCR エントリのサンプル（box 座標付き）"""
    return [
        {"text": "山田 太郎", "confidence": 0.95, "box": [[50, 100], [200, 100], [200, 140], [50, 140]]},
        {"text": "あおばクリニック", "confidence": 0.92, "box": [[50, 160], [300, 160], [300, 200], [50, 200]]},
        {"text": "3,800", "confidence": 0.88, "box": [[400, 300], [480, 300], [480, 340], [400, 340]]},
        {"text": "2026/01/15", "confidence": 0.90, "box": [[50, 50], [200, 50], [200, 80], [50, 80]]},
    ]

@pytest.fixture
def mock_ocr_json():
    """process_input_json の入力形式の OCR JSON"""
    return [dict(entry) for entry in sample_ocr_entries()]

@pytest.fixture
def temp_db(tmp_path):
    """スキーマ適用済みの一時 DB"""
    from app.db import get_db_connection
    schema_path = Path(__file__).parents[2] / "docs" / "schema.sql"
    db_file = tmp_path / "test.sqlite3"
    conn = get_db_connection(db_file)
    conn.executescript(schema_path.read_text())
    conn.close()
    return db_file
```

## テストケース一覧

### Task 2-A: `tests/test_coord_search.py` に追加 — 座標近接検索

#### TC-A01: 同一座標での完全マッチ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_search_by_proximity_exact` |
| 概要 | テンプレート座標と同一の box を持つ OCR エントリが正しく検索される |
| 確認点 | 戻り値が当該エントリの dict であること / text, confidence, box が正しいこと |

#### TC-A02: しきい値内のズレでマッチ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_search_by_proximity_within_threshold` |
| 概要 | テンプレート座標から 10px 程度ずれていてもしきい値 20px 以内ならマッチする |
| 確認点 | 最も近い OCR エントリが返ること |

#### TC-A03: しきい値超過で None

| 項目 | 内容 |
|------|------|
| テスト名 | `test_search_by_proximity_beyond_threshold` |
| 概要 | テンプレート座標から 50px 以上離れている場合、None が返る |
| 確認点 | 戻り値が None であること |

#### TC-A04: 空エントリで None

| 項目 | 内容 |
|------|------|
| テスト名 | `test_search_by_proximity_empty_entries` |
| 概要 | OCR エントリが空リストの場合 None を返す |
| 確認点 | 戻り値が None であること |

#### TC-A05: 空 target_box で None

| 項目 | 内容 |
|------|------|
| テスト名 | `test_search_by_proximity_empty_target` |
| 概要 | target_box が空の場合 None を返す |
| 確認点 | 戻り値が None であること |

#### TC-A06: 複数候補から最小距離を選択

| 項目 | 内容 |
|------|------|
| テスト名 | `test_search_by_proximity_nearest_match` |
| 概要 | 複数の OCR エントリがある場合、最も近いものが選択される |
| 確認点 | 最も近いエントリの box が返ること |

#### TC-A07: 複数フィールド一括検索

| 項目 | 内容 |
|------|------|
| テスト名 | `test_search_by_proximity_multi` |
| 概要 | `search_by_proximity_multi()` で複数フィールドの座標を一括検索する |
| 確認点 | 全フィールドの結果が正しいこと |

#### TC-A08: 一部フィールドのみマッチ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_search_by_proximity_multi_partial` |
| 概要 | 一部フィールドがしきい値を超えている場合、該当フィールドのみ None になる |
| 確認点 | マッチしたフィールドは dict / マッチしなかったフィールドは None |

### Task 2-B: `tests/test_structural_parser.py` 新規 — テンプレート連携 + パイプライン

#### TC-B01: raw_data.json → structured_data.json 生成

| 項目 | 内容 |
|------|------|
| テスト名 | `test_process_input_json_creates_structured_json` |
| 概要 | MockLLMClient で raw_data.json を処理すると structured_data.json が生成される |
| 確認点 | 出力ファイルが存在 / JSON がパース可能 / name, clinic, amount, date が含まれる |

#### TC-B02: テンプレート座標で抽出値を上書き

| 項目 | 内容 |
|------|------|
| テスト名 | `test_template_based_extraction_override` |
| 概要 | DB にテンプレートが存在する場合、座標近接検索の結果で抽出値が上書きされる |
| 準備 | DB に clinic + template（amount の座標）を事前登録 / ocr_json の amount テキストを変更してズレを作る |
| 確認点 | `amount` の値が座標近接で見つかったテキストで上書きされていること |

#### TC-B03: テンプレートマッチなし → 通常抽出維持

| 項目 | 内容 |
|------|------|
| テスト名 | `test_template_no_match_falls_back` |
| 概要 | テンプレートの座標が OCR 結果とマッチしない場合、MockLLMClient の抽出結果が維持される |
| 確認点 | 出力が MockLLMClient の通常抽出結果と一致すること |

#### TC-B04: db_path=None でテンプレート連携スキップ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_template_without_db_skips` |
| 概要 | `db_path=None` の場合、テンプレート連携がスキップされる |
| 確認点 | 出力が MockLLMClient の通常抽出結果と一致 / エラーが発生しない |

#### TC-B05: clinic 未検出でテンプレート連携スキップ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_template_without_clinic_skips` |
| 概要 | clinic が抽出されなかった場合、テンプレート連携がスキップされる |
| 確認点 | 出力の clinic が None / エラーが発生しない |

### Task 1: `tests/test_watcher_integration.py` に追加 — パイプライン確認

#### TC-C01: watcher → structured_data 生成

| 項目 | 内容 |
|------|------|
| テスト名 | `test_pipeline_generates_structured_data` |
| 概要 | FakeOCR + scan_and_process で画像処理後、raw_data.json と structured_data.json の両方が生成される |
| 確認点 | raw_data.json が存在 / structured_data.json が存在 / 両方パース可能 |

## エッジケース一覧

| ケース | 対応方針 |
|--------|---------|
| box 座標が不正形式 | `_calculate_box_center` で IndexError → caller が None 扱い |
| ocr_json が text_lines 形式（box なし） | 近接検索をスキップ（box がないため） |
| テンプレート | coords_corrections が空 dict の場合 → 近接検索結果も空 → 上書きなし |
| 同一 box に複数フィールドが該当 | 各フィールド個別に近接検索するため問題なし |
| process_input_json の ocr_entries が期待形式と異なる | `isinstance` チェックで防御 |

## テスト実行方法

```bash
# Task 2-A: 座標近接検索の単体テスト
pytest tests/test_coord_search.py::test_search_by_proximity_exact -v

# Task 2-B: テンプレート連携のテスト
pytest tests/test_structural_parser.py -v

# Task 1: パイプラインテスト
pytest tests/test_watcher_integration.py::test_pipeline_generates_structured_data -v

# 全テスト
pytest tests/test_coord_search.py tests/test_structural_parser.py tests/test_watcher_integration.py -v

# 既存テストとの互換性確認
pytest tests/ -v

# フォーマット確認
black --check .
```
