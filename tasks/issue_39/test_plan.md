# Issue #39: テスト計画

## テスト戦略

- **フレームワーク**: pytest / conftest.py（`PYTHONPATH=.` 有効化）
- **新規テストファイル**:
  - `tests/test_date_anchor.py` — date anchor 解決の単体テスト
  - `tests/test_migrations.py` — `coord_basis` 列 migration の idempotency テスト
- **既存テスト拡張**: `test_coord_normalizer.py`, `test_coord_search.py`, `test_db.py`, `test_feedback.py`, `test_coordinate_service.py`, `test_structural_parser.py`, `test_image_processing_service.py`, `test_receipt_processor.py`, `test_web.py`
- **テストデータ**: issue_32 の `SAMPLE_OCR_ENTRIES` スタイル（`{text, confidence, box}`）のリストを再利用し、日付候補を複数持つパターンを追加。

## テストケース一覧

### Task 1: `tests/test_date_anchor.py` — date anchor 照合・座標変換

#### TC-01: テキスト一致の単一候補 → anchor 採用

| 項目 | 内容 |
|------|------|
| テスト名 | `test_resolve_anchor_single_candidate` |
| 概要 | 構造化 date と同値の OCR 日付がちょうど 1 件ある場合、その box が返る |
| 確認点 | `resolve_date_anchor()` が当該 box を返す |

#### TC-02: date 未学習（template date box なし）→ 従来方式（Q2 案A の場合）

| 項目 | 内容 |
|------|------|
| テスト名 | `test_resolve_anchor_no_template_box` |
| 概要 | template date coords が未学習（`None`）で、テキスト一致が 1 件でも anchor を採用しない |
| 確認点 | `None` を返す（従来方式）|

#### TC-03: 一致なし → fallback

| 項目 | 内容 |
|------|------|
| テスト名 | `test_resolve_anchor_no_text_match` |
| 概要 | 構造化 date と一致する OCR 日付候補がない |
| 確認点 | `None` を返す |

#### TC-04: 重複日付（複数候補・距離で一意）→ 採用

| 項目 | 内容 |
|------|------|
| テスト名 | `test_resolve_anchor_duplicate_unique_by_proximity` |
| 概要 | 同じ日付が 2 箇所あるが、template date box に 50px 以内で一意に近い方がある |
| 確認点 | 近い方の box を返す |

#### TC-05: 重複日付で曖昧（競合）→ fallback

| 項目 | 内容 |
|------|------|
| テスト名 | `test_resolve_anchor_ambiguous` |
| 概要 | 複数候補が距離的に競合し一意に決まらない |
| 確認点 | `None` を返す |

#### TC-06: 表記ゆれ許容

| 項目 | 内容 |
|------|------|
| テスト名 | `test_resolve_anchor_variant_format` |
| 概要 | `2026/01/15` と `2026年1月15日` が同じ日付として照合される |
| 確認点 | 候補として一致する |

#### TC-07: structured_date 不正

| 項目 | 内容 |
|------|------|
| テスト名 | `test_resolve_anchor_invalid_date` |
| 概要 | structured_date が `parse_date()` 不能 |
| 確認点 | `None` を返す |

#### TC-08: box 基準での再正規化

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_by_anchor` |
| 概要 | `normalize_coordinates_by_anchor()` が anchor box 左上を offset に全 box を減算し raw を上書き |
| 確認点 | offset が正しい、`normalized=True` |

#### TC-09: box 基準再正規化・無効 anchor

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_by_anchor_invalid` |
| 概要 | anchor_box が 4 点未満・空の場合 |
| 確認点 | `normalized=False`、ファイル変更なし |

### Task 2: `tests/test_migrations.py` / `tests/test_db.py` — template 基準移行

#### TC-10: 新規 DB に coord_basis 列が存在

| 項目 | 内容 |
|------|------|
| テスト名 | `test_schema_has_coord_basis_column` |
| 概要 | `run_migrations()` 適用後の新規 DB で `coord_basis` が存在しデフォルト `'topmost'` |
| 確認点 | `PRAGMA table_info(templates)` に `coord_basis` |

#### TC-11: 既存 DB へ idempotent に列追加

| 項目 | 内容 |
|------|------|
| テスト名 | `test_migration_adds_column_idempotent` |
| 概要 | coord_basis 列なし DB に適用しても 2 回目はエラーなし |
| 確認点 | 2 回連続 `run_migrations()` で例外なし |

#### TC-12: update_template_basis で履歴保存 + coord_basis='date'

| 項目 | 内容 |
|------|------|
| テスト名 | `test_update_template_basis_writes_history` |
| 概要 | 基準切替時に旧 topmost coords が `template_history`（change_reason=`basis_migration`）に残り、coords が date 基準へ更新され `coord_basis='date'` |
| 確認点 | history に旧値、template に新値・basis |

#### TC-13: 二重変換防止

| 項目 | 内容 |
|------|------|
| テスト名 | `test_update_template_basis_skips_if_already_date` |
| 概要 | 既に `coord_basis='date'` の template に再度呼んでも変換しない |
| 確認点 | coords ・ history 不変 |

#### TC-14: 更新失敗でロールバック

| 項目 | 内容 |
|------|------|
| テスト名 | `test_update_template_basis_rollback_on_error` |
| 概要 | 途中で例外発生した場合、history / template が部分更新されない |
| 確認点 | 変更が適用されていない |

### Task 3: 処理経路テスト

#### TC-15: 画像 OCR で date anchor → 全 box が date 基準

| 項目 | 内容 |
|------|------|
| テスト名 | `test_image_processing_uses_date_anchor`（`test_image_processing_service.py`）|
| 概要 | clinic に template date coords あり + 信頼できる候補がある画像 OCR で、raw / structured / DB box が date 基準 |
| 確認点 | anchor box 左上が (0,0)、structured・DB も同基準 |

#### TC-16: 未学習 clinic は従来方式維持

| 項目 | 内容 |
|------|------|
| テスト名 | `test_image_processing_unlearned_fallback` |
| 概要 | template date coords がない clinic では従来の topmost 正規化 |
| 確認点 | 既存の検証と同じ offset 挙動 |

#### TC-17: 既存 OCR JSON 経路の互換性

| 項目 | 内容 |
|------|------|
| テスト名 | `test_input_json_path_compatible`（`test_structural_parser.py`）|
| 概要 | `--input-json` 経路で anchor 未学習 / 曖昧時は従来結果 |
| 確認点 | 従来の structured 結果と一致 |

#### TC-18: low-confidence / preprocessing retry 維持

| 項目 | 内容 |
|------|------|
| テスト名 | `test_low_confidence_anchor_after_gate`（`test_receipt_processor.py`）|
| 概要 | low-confidence 時も前処理 retry が従来通り動作し、anchor は低 Confidence 判定後に実行 |
| 確認点 | retry 発生、フラグ反映 |

### Task 3/4: 修正フロー・近傍検索の新基準継続

#### TC-19: 基準切替後の近傍検索

| 項目 | 内容 |
|------|------|
| テスト名 | `test_proximity_search_on_date_basis`（`test_coordinate_service.py`）|
| 概要 | date 基準へ切替済み template の coords で修正時の近傍検索が機能する |
| 確認点 | 修正時に座標が正しく解決される |

#### TC-20: 近接値しきい値・既存挙動の非回帰

| 項目 | 内容 |
|------|------|
| テスト名 | `test_proximity_threshold_unchanged` |
| 概要 | `DEFAULT_PROXIMITY_THRESHOLD` が 50.0、confidence 0.8 が既存のまま |
| 確認点 | 定数値 |

## エッジケース一覧

| ケース | 対応方針 |
|--------|---------|
| structured_date が None / 不正 | anchor 解決せず従来方式 |
| 日付表現のバリエーション（`/`・`年`・`−`・和暦） | `parse_date()` で統一比較 |
| 同じ日付の複数出現 | template coords の距離で一意判定し、曖昧なら fallback |
| template date coords 未学習 | 従来方式（受入条件 1）|
| template coords が不正 box | `search_by_proximity()` が `None` → fallback |
| 既存 DB（coord_basis 列なし） | idempotent ALTER |
| 二重変換（date 基準済み） | `coord_basis='date'` スキップ |
| 基準切替の途中失敗 | ロールバック（部分更新防止）|
| low-confidence | 従来の gate / retry を維持 |

## テスト実行方法

```bash
# date anchor 単体
pytest tests/test_date_anchor.py -v

# migration / DB
pytest tests/test_migrations.py tests/test_db.py -v

# 対象回帰群
pytest tests/test_coord_normalizer.py tests/test_coordinate_service.py tests/test_coord_search.py \
       tests/test_feedback.py tests/test_structural_parser.py tests/test_web.py -v

# 処理経路
pytest tests/test_image_processing_service.py tests/test_receipt_processor.py -v

# 全テスト（既存 + 新規）
pytest tests/ -v

# フォーマット
black --check .
```
