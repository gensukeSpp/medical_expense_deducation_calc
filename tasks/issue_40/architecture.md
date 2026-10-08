# Issue #40: アーキテクチャ設計 — 前方テンプレート補正の基底不一致修正（案B）

## 全体データフロー（修正後の前方補正判定）

```mermaid
graph TD
    PARSE["_parse_structured (process_input_json)"] --> APPLY["ExtractionService._apply_template_corrections()"]
    APPLY --> CLINIC["clinic 特定 (①② complete/text-similarity)"]
    CLINIC --> TEMPLATE["get_latest_template_by_clinic()<br/>→ coord_basis を取得"]
    TEMPLATE --> GATE{"coord_basis == 'date'?"}
    GATE -->|date 移行済み| SKIP["座標ベース上書きをスキップ<br/>(search_fields_by_proximity 不実行)"]
    GATE -->|topmost (未移行)| NORMAL["従来どおり座標上書き"]
    SKIP --> CLINICFIX["clinic 名の正しい名へ上書き (③)"]
    NORMAL --> CLINICFIX
    CLINICFIX --> NEWCLINIC["template 未取得なら新規 clinic 作成 (④)"]
```

## 修正対象モジュール

| モジュール | 変更内容 | 備考 |
|-----------|---------|------|
| `app/structural_parser.py` | `_apply_template_corrections()` に `coord_basis=='date'` ガードを追加 | 修正対象の中核 |
| `app/db.py` | 変更なし（`get_latest_template_by_clinic` が coord_basis を返すのは #39 済み）| 参考のみ |
| `app/services/image_processing_service.py` / `receipt_processor.py` | 変更なし | 前方補正は共通の `process_input_json` 経由のため 1箇所の修正で両方に効く |

## 変更しないモジュール

| モジュール | 理由 |
|-----------|------|
| `app/date_anchor.py` | anchor 正規化・template 移行は #39 のまま |
| `app/coord_normalizer.py` | 座標正規化 API は不変 |
| `app/db.py` | `coord_basis` 列・`get_latest_template_by_clinic` は #39 で対応済み |
| `app/db_migrations.py` / `docs/schema.sql` | schema 変更なし |
| 処理経路サービス | 共通の `ExtractionService` を利用するため直接変更不要 |

## `_apply_template_corrections()` の修正詳細

### 現状（structural_parser.py:82-166）

1. clinic 特定 → template 取得。
2. `if template and matched_clinic_name:` → `coords = template.get("coords_corrections")` があれば
   `search_fields_by_proximity(ocr_entries, coords, threshold=...)` で各フィールド値を上書き。
3. `matched_clinic_name != clinic_name` なら clinic 名を上書き。
4. template なしなら新規 clinic 作成。

### 修正（案B・粒度1）

`coords` による上書きブロックを `coord_basis=='date'` のときスキップする。

```python
# structural_parser.py _apply_template_corrections() 内、テンプレート適用ブロック
if template and matched_clinic_name:
    coord_basis = template.get("coord_basis") or "topmost"
    # 移行済み（date 基準）の template は、topmost 基準の raw に照合できないため
    # 座標ベースのフィールド上書きをスキップする（Issue #40, 案B 粒度1）。
    # ※ 誤上書き防止が目的。値はテキスト抽出（LLM）にフォールバック。
    if coord_basis != "date":
        coords = template.get("coords_corrections")
        if coords:
            ocr_entries = self._get_ocr_entries(ocr_json)
            if ocr_entries:
                proximity_texts = search_fields_by_proximity(
                    ocr_entries,
                    coords,
                    threshold=DEFAULT_PROXIMITY_THRESHOLD,
                )
                for field_name, concat_text in proximity_texts.items():
                    if concat_text and field_name in extracted:
                        extracted[field_name] = concat_text

    # 正しいクリニック名で上書き（③）は coord_basis に関係なく常に実行
    if matched_clinic_name != clinic_name:
        extracted["clinic"] = matched_clinic_name
```

### 影響

- 移行済み clinic: ②のフィールド上書きが走らない → 誤上書きが防止される。③④は従来どおり。
- 未移行 clinic（`coord_basis=='topmost'` または旧データで NULL）: `coord_basis != "date"` が真なので従来動作。

### 補足（①のレイアウトマッチングについて）

- `match_template_by_layout`（layout matching）も `coords_corrections` を使うが、これは
  **name 解決（完全一致/類似度）で template が見つからなかった場合のみ**走る分岐（Step 3）。
- 移行済み clinic であっても name 解決で template が得られればこの分岐に入らないため、
  実質的に誤マッチの恐れは低い。ただし完全に排他するなら、この分岐にも `coord_basis` ガードを
  追加してもよい（今回は対象外として記録）。

## エラーハンドリング

| シナリオ | 対応 |
|---------|------|
| `template` がない / `coord_basis` が None（旧データ） | `or "topmost"` で従来動作 |
| `coord_basis == 'date'` | 座標上書きをスキップ（誤上書き防止）|
| `search_fields_by_proximity` が例外 | 既存の try/except（`logger.error`）で握る（変更なし）|
| 存在しない clinic | 新規 clinic 作成（④、変更なし）|