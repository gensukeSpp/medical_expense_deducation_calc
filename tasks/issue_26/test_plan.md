# Issue #26: テスト計画

## テスト戦略

- **フレームワーク**: pytest
- **DB**: `tmp_path` フィクスチャで一時 SQLite DB を作成（`tests/test_web.py` の `temp_db` パターンを踏襲）
- **既存のフィクスチャ流用**: `tests/test_web.py` の `temp_output_dir`、`temp_db`、`client` フィクスチャを活用
- **新規フィクスチャ**: 必要に応じて `test_web.py` に `temp_ocr_data` 等を追加

## テストケース一覧

### Task 1: `tests/test_normalization.py` に追加 — parse_amount プレーン数字対応

#### TC-01: プレーン数字のパース

| 項目 | 内容 |
|------|------|
| テスト名 | `test_parse_amount_plain_number` |
| 概要 | `"3800"` → `3800` のようにプレーンな数字文字列が正しくパースされる |
| 確認点 | 戻り値が int 3800 であること |

#### TC-02: カンマ区切りの数字パース

| 項目 | 内容 |
|------|------|
| テスト名 | `test_parse_amount_comma_separated` |
| 概要 | `"3,800"` → `3800` のようにカンマ区切りの数字文字列が正しくパースされる |
| 確認点 | 戻り値が int 3800 であること |

#### TC-03: 空文字列は None

| 項目 | 内容 |
|------|------|
| テスト名 | `test_parse_amount_empty_string` |
| 概要 | 空文字列は None を返す |
| 確認点 | 戻り値が None であること |

#### TC-04: 不正文字列は None（既存動作維持）

| 項目 | 内容 |
|------|------|
| テスト名 | `test_parse_amount_non_numeric_string` |
| 概要 | `"abc"` などの非数字文字列は None を返す |
| 確認点 | 戻り値が None であること |

#### TC-05: 既存の日本語形式は引き続き動作

| 項目 | 内容 |
|------|------|
| テスト名 | `test_parse_amount_existing_formats_unchanged` |
| 概要 | 既存の `"3,800円"` → 3800、`"一万二千円"` → 12000 が引き続き動作する |
| 確認点 | 戻り値が従来通りであること |

### Task 2: `tests/test_web.py` に追加 — clinic_id UPDATE

#### TC-06: 修正後 clinic_id が DB に反映される

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_sets_clinic_id` |
| 概要 | PUT 修正後、`receipts` テーブルの `clinic_id` が NULL ではなくなっている |
| 準備 | `temp_output_dir` の structured データに `clinic: "あおばクリニック"` を含める |
| 確認点 | DB の `SELECT clinic_id FROM receipts WHERE id = ?` が NULL でないこと |

#### TC-07: clinic なし修正でも clinic_id は NULL のまま（既存動作）

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_without_clinic_keeps_clinic_id_null` |
| 概要 | clinic が None のレシートの修正では clinic_id は NULL のまま |
| 確認点 | DB の `clinic_id` が NULL であること |

### Task 3: `tests/test_web.py` に追加 — テンプレート連携改善

#### TC-08: テンプレートテーブルにデータが挿入される

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_creates_template` |
| 概要 | 修正時に座標が検出できた場合、`templates` テーブルにレコードが作成される |
| 準備 | raw_data JSON ファイルも配置（OCR エントリ付き） |
| 確認点 | `SELECT COUNT(*) FROM templates WHERE clinic_id = ?` > 0 |

#### TC-09: raw_data なしでも修正は正常動作

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_without_raw_data_continues` |
| 概要 | raw_data JSON ファイルが存在しなくても修正処理は継続される |
| 確認点 | JSON ファイルが更新され、エラーが発生しないこと |

### Task 4: `tests/test_watcher.py` または専用テスト

#### TC-10: watcher 単独実行で引数が正しく伝播される

| 項目 | 内容 |
|------|------|
| テスト名 | `test_watcher_standalone_args_compatible` |
| 概要 | `watcher.parse_args()`（または `setup_args()`）が `main.py` と同じ引数体系を提供する |
| 確認点 | `model` / `db-path` 引数が含まれていること |

## エッジケース一覧

| ケース | 対応方針 |
|--------|---------|
| 金額にマイナス記号（"-500"） | `isdigit()` が False を返す → None 維持。現状と変わらず |
| 金額に小数点（"3800.50"） | `isdigit()` が False → None。整数値のみ対応 |
| raw_data ファイルが glob で複数ヒット | `sorted()` で最新（最終）を使用 |
| raw_data ファイルが glob で 0 件 | None → 座標フィードバック全体をスキップ |
| DB 未接続（db_path=None） | 既存の条件分岐でスキップ。本タスクでは変更なし |
| watcher.py を直接 `python app/watcher.py` で起動 | `setup_args()` が全引数を定義するため動作は変わらず |

## テスト実行方法

```bash
# Task 1: parse_amount 拡張のテスト
pytest tests/test_normalization.py -v

# Task 2 + 3: Web UI 修正の結合テスト
pytest tests/test_web.py -v

# Task 4: watcher 引数互換性のテスト
pytest tests/test_watcher_integration.py -v

# 全テスト（既存テストとの互換性確認）
pytest tests/ -v

# フォーマット確認
black --check .
```