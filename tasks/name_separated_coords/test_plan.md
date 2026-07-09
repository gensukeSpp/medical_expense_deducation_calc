# Test Plan: 分割氏名の自動マルチボックス対応

## ユニットテスト

### `tests/test_coord_search.py` に追加

| # | テスト名 | 内容 |
|---|---|---|
| 1 | `test_is_multi_box_true` | マルチbox形式 → `True` |
| 2 | `test_is_multi_box_false_single` | 単一box形式 → `False` |
| 3 | `test_is_multi_box_false_invalid` | 不正データ → `False` |
| 4 | `test_search_fields_by_proximity_single` | 単一box → 単一テキスト返却 |
| 5 | `test_search_fields_by_proximity_multi` | マルチbox → 連結テキスト返却 |
| 6 | `test_search_fields_by_proximity_multi_with_sama` | 「様」サフィックス除去 |
| 7 | `test_search_fields_by_proximity_threshold` | 閾値超過 → None |

**テストデータ**（マルチbox用）:

```python
MULTI_BOX_NAME = [
    [[67, 126], [205, 130], [203, 198], [65, 194]],
    [[255, 126], [379, 135], [374, 209], [250, 200]],
]

OCR_ENTRIES_SPLIT_NAME = [
    {"text": "山田",   "confidence": 0.99, "box": [[67,126],[205,130],[203,198],[65,194]]},
    {"text": "太郎様", "confidence": 0.91, "box": [[255,126],[379,135],[374,209],[250,200]]},
]
```

### `tests/test_structural_parser.py` に追加

| # | テスト名 | 内容 |
|---|---|---|
| 8 | `test_apply_template_multi_box` | マルチboxテンプレート → 連結テキストで上書きされる |
| 9 | `test_apply_template_multi_box_single_unchanged` | 単一boxテンプレート → 従来通り動作 |
| 10 | `test_apply_template_no_template` | テンプレートなし → 変更なし |

### `tests/test_coordinate_service.py` に追加

| # | テスト名 | 内容 |
|---|---|---|
| 11 | `test_process_feedback_multi_box_fallback` | テキスト検索失敗 → サブストリングフォールバック → マルチbox |
| 12 | `test_process_feedback_no_fallback_single_ok` | テキスト検索成功 → フォールバック不要 |
| 13 | `test_process_feedback_fallback_low_similarity` | 連結後の類似度不足 → フォールバック reject |
| 14 | `test_process_feedback_multi_line_reject` | 別ラインのサブストリング → reject |

## 既存テスト回帰確認

```bash
pytest -q
```

全テストケースが変更前と変わらずパスすること（78 passed, 4 known failures）。

特に以下のテストが影響を受ける可能性があるため、Task 2 完了後に重点確認:

- `tests/test_coord_search.py` — 既存の近接検索テスト
- `tests/test_feedback.py` — `process_correction_feedback()` のテスト
- `tests/test_integration.py` — パイプライン統合テスト（存在すれば）

## 手動テスト手順

### 準備

```bash
# テスト用の分割氏名 raw_data を output_json/ に配置
cp tests/fixtures/split_name_raw_data.json output_json/
```

### テスト実行

```bash
# 1. OCR→構造化抽出（テンプレートなし）
uv run main.py --image-name split_name_test.jpg

# 2. Web UI で修正
uv run main.py --serve --db-path data/db.sqlite3
# → name フィールドを "山田太郎" に修正

# 3. テンプレート確認
sqlite3 data/db.sqlite3 "SELECT coords_corrections FROM templates;"
# → name がマルチbox形式で保存されていることを確認

# 4. 再抽出（テンプレートあり）
# 同じクリニックの別レシートを処理
uv run main.py --image-name another_receipt.jpg
# → name が正しく "山田太郎" として抽出されることを確認
```