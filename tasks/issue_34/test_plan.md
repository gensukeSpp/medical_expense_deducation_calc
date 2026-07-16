# Issue #34: テスト計画

## テスト戦略

- **フレームワーク**: pytest
- **DB**: `tmp_path` フィクスチャ + `run_migrations()` で一時SQLite DBを作成（既存パターンを踏襲）
- **OCRエントリ**: 既存の `SAMPLE_OCR_ENTRIES` / `sample_ocr_entries` フィクスチャを流用
- **テキスト類似度**: `difflib.SequenceMatcher` のテストは `test_coord_search.py` に追加
- **結合テスト**: `test_structural_parser.py` にハイブリッドマッチングの結合テストを追加

## テスト用フィクスチャ（追加）

### `tests/test_coord_search.py` 内

```python
@pytest.fixture
def sample_clinics():
    """全クリニック一覧のモック"""
    return [
        {"id": "uuid-1", "name": "ABCクリニック", "created_at": "2026-01-01"},
        {"id": "uuid-2", "name": "あおばクリニック", "created_at": "2026-01-02"},
        {"id": "uuid-3", "name": "デンタルクリニック", "created_at": "2026-01-03"},
    ]
```

### `tests/test_structural_parser.py` 内

```python
@pytest.fixture
def seed_clinic_misspelled_match(temp_db: Path) -> str:
    """ABCクリニックのテンプレート + 誤抽出用OCRエントリ"""
    pass  # テストケース内で実装
```

## テストケース一覧

### Task 1-A: `tests/test_db.py` に追加 — 新規DB関数

#### TC-DB01: `get_all_clinics` 正常系

| 項目 | 内容 |
|------|------|
| テスト名 | `test_get_all_clinics` |
| 概要 | 複数クリニックを登録後、全件が取得できる |
| 確認点 | 取得件数が登録数と一致 / 各レコードに id, name が含まれる |

#### TC-DB02: `get_all_clinics` 空DB

| 項目 | 内容 |
|------|------|
| テスト名 | `test_get_all_clinics_empty` |
| 概要 | クリニック未登録時に空リストが返る |
| 確認点 | 戻り値が空リスト |

#### TC-DB03: `get_all_templates_with_names` 正常系

| 項目 | 内容 |
|------|------|
| テスト名 | `test_get_all_templates_with_names` |
| 概要 | テンプレートがクリニック名付きで取得できる |
| 確認点 | 各テンプレートに clinic_name が含まれる / coords_corrections が JSON デコード済み |
| 注意 | 複数バージョンがある場合、最新版のみ取得されること |

#### TC-DB04: `get_all_templates_with_names` 空DB

| 項目 | 内容 |
|------|------|
| テスト名 | `test_get_all_templates_with_names_empty` |
| 概要 | テンプレート未登録時に空リストが返る |
| 確認点 | 戻り値が空リスト |

### Task 1-B: `tests/test_coord_search.py` に追加 — マッチング関数

#### TC-CS01: テキスト類似度 — 完全一致

| 項目 | 内容 |
|------|------|
| テスト名 | `test_find_clinic_by_text_similarity_exact` |
| 概要 | 完全一致するクリニック名が正しくマッチする |
| 確認点 | 戻り値の name が入力と一致 |

#### TC-CS02: テキスト類似度 — 文字欠け

| 項目 | 内容 |
|------|------|
| テスト名 | `test_find_clinic_by_text_similarity_partial` |
| 概要 | "BCクリニック" → "ABCクリニック" がマッチする |
| 確認点 | 戻り値の name が "ABCクリニック" |
| 備考 | 類似度は normalize_text 後で ~0.86 程度になる |

#### TC-CS03: テキスト類似度 — マッチなし

| 項目 | 内容 |
|------|------|
| テスト名 | `test_find_clinic_by_text_similarity_no_match` |
| 概要 | 全く異なる文字列で None が返る |
| 確認点 | 戻り値が None |

#### TC-CS04: テキスト類似度 — 空入力

| 項目 | 内容 |
|------|------|
| テスト名 | `test_find_clinic_by_text_similarity_empty` |
| 概要 | 空文字列で None が返る |
| 確認点 | 戻り値が None |

#### TC-CS05: 座標レイアウト — 全フィールド一致

| 項目 | 内容 |
|------|------|
| テスト名 | `test_match_template_by_layout_exact` |
| 概要 | 全フィールドの座標が近接マッチする場合、テンプレートが返る |
| 確認点 | 戻り値の clinic_name が正しい |

#### TC-CS06: 座標レイアウト — 部分一致

| 項目 | 内容 |
|------|------|
| テスト名 | `test_match_template_by_layout_partial` |
| 概要 | 3フィールド中2フィールドマッチ（66%, 閾値0.6以上）でテンプレートが返る |
| 確認点 | 戻り値が None でない |

#### TC-CS07: 座標レイアウト — マッチ率不足

| 項目 | 内容 |
|------|------|
| テスト名 | `test_match_template_by_layout_no_match` |
| 概要 | 3フィールド中1フィールドのみマッチ（33%, 閾値0.6未満）で None |
| 確認点 | 戻り値が None |

#### TC-CS08: 座標レイアウト — 空エントリ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_match_template_by_layout_empty` |
| 概要 | OCRエントリが空の場合 None |
| 確認点 | 戻り値が None |

### Task 1-C: `tests/test_structural_parser.py` に追加 — ハイブリッドフォールバック

#### TC-SP01: 完全一致 — 従来通り動作（後方互換性）

| 項目 | 内容 |
|------|------|
| テスト名 | `test_hybrid_exact_match_first` |
| 概要 | クリニック名が完全一致する場合、Step1 でテンプレートが適用される |
| 確認点 | 従来の `test_template_based_extraction_override` と同等の結果 |

#### TC-SP02: テキスト類似度マッチング

| 項目 | 内容 |
|------|------|
| テスト名 | `test_hybrid_text_similarity_fallback` |
| 概要 | クリニック名に文字欠けがある場合、Step2 でテンプレートが適用される |
| 準備 | DBに "ABCクリニック" のテンプレートを登録 / OCRエントリのclinic名を "BCクリニック" に設定 |
| 確認点 | amount や date がテンプレート座標から補正される / clinic 名が "ABCクリニック" に上書きされる |

#### TC-SP03: 座標レイアウトマッチング

| 項目 | 内容 |
|------|------|
| テスト名 | `test_hybrid_layout_fallback` |
| 概要 | クリニック名が全く異なるが座標レイアウトが一致する場合、Step3 でテンプレートが適用される |
| 準備 | DBに "ABCクリニック" のテンプレートを登録 / OCRエントリのclinic名を "全然違う名前" に設定 |
| 確認点 | テンプレート座標から amount/date が補正される / clinic 名が "ABCクリニック" に上書きされる |

#### TC-SP04: 全マッチ失敗 → 従来フロー

| 項目 | 内容 |
|------|------|
| テスト名 | `test_hybrid_all_fallback_no_match` |
| 概要 | いずれのマッチングも失敗した場合、従来通り新規クリニックとして処理される |
| 準備 | DBに既存テンプレートなし / OCRエントリのclinic名が既存クリニックと全く異なる |
| 確認点 | 結果が MockLLMClient の通常抽出結果と一致 / DBに新規クリニックが作成される |

## エッジケース一覧

| ケース | 対応方針 |
|--------|---------|
| テキスト類似度で複数クリニックが同率 | 最初に見つかったものを採用（`>` で更新、`>=` ではない） |
| 座標レイアウトでテンプレートが1件もない | 空リストを返し、従来フローへ |
| coords_corrections が空 dict の場合 | `match_template_by_layout` でスキップ（fields が空） |
| OCRエントリが text_lines 形式（box なし） | `_get_ocr_entries()` で空リストを返す → 座標レイアウトマッチングスキップ |
| クリニック名が空文字の場合 | `_apply_template_corrections` 冒頭で return |
| テキスト類似度の normalize_text 結果が空 | 該当クリニックをスキップ |
| 座標レイアウトマッチングで同じ rate のテンプレートが複数 | 最初に処理されたテンプレートを採用（`>` による更新） |

## テスト実行方法

```bash
# Task 1-A: DB関数の単体テスト
pytest tests/test_db.py::test_get_all_clinics tests/test_db.py::test_get_all_clinics_empty -v

# Task 1-B: マッチング関数の単体テスト
pytest tests/test_coord_search.py::test_find_clinic_by_text_similarity_exact -v
pytest tests/test_coord_search.py::test_match_template_by_layout_exact -v

# Task 1-C: ハイブリッドフォールバックの結合テスト
pytest tests/test_structural_parser.py::test_hybrid_text_similarity_fallback -v
pytest tests/test_structural_parser.py::test_hybrid_layout_fallback -v

# 全テスト
pytest tests/test_db.py tests/test_coord_search.py tests/test_structural_parser.py -v

# 既存テストとの互換性確認
pytest tests/ -v

# フォーマット確認
black --check .
```