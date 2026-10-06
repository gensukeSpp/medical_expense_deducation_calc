# Issue #39: 日付基準による OCR box 座標正規化

## 目的

現在は OCR 結果の全 box から最小 x/y を求め、`raw_data.json` の座標をその基準（topmost/leftmost）で正規化している。構造化出力の `date` は領収書内の複数の日付候補から抽出されることがあるため、どの OCR box が抽出元か分からないまま、日付を基準にした正規化へ直接は切り替えられない。

本 Issue では、フォーム修正で `templates.coords_corrections["date"]` が学習された後、次回以降の同 clinic/layout でその座標を手がかりに日付候補を選び、信頼できる場合に**選択した date box の左上を基準に全 OCR box を再正規化**する。初回・date 座標未学習・候補が曖昧な場合は従来の topmost/leftmost 基準を維持する。

## 参照

- [Issue #39 本体](../../../issues/39)
- [Issue #32 実装](../../tasks/issue_32/tasks.md) — 座標相対化 + low_confidence gate（本機能の土台）
- [Issue #36 実装](../../tasks/issue_36/plan.md) — OCR 前処理・low-confidence 再試行
- `app/coord_normalizer.py` — `normalize_coordinates()` / `_find_min_coords()` / `get_topmost_confidence()`
- `app/normalization.py` — `parse_date()` / `normalize_text()`
- `app/coord_search.py` — `search_coordinates()` / `search_by_proximity()` / `search_by_proximity_multi()` / `match_template_by_layout()`
- `app/structural_parser.py` — `ExtractionService._apply_template_corrections()` / `DEFAULT_PROXIMITY_THRESHOLD` / `ReceiptProcessingService`
- `app/services/image_processing_service.py` — `ImageProcessingService.process()`
- `app/services/receipt_processor.py` — `ReceiptProcessor._sync_process()`
- `app/services/ocr_coordinate_service.py` — `_resolve_coord_results()` / `process_feedback()`
- `app/template_feedback.py` — `process_correction_feedback()`
- `app/db.py` — `upsert_template()` / `insert_template_history()` / `get_latest_template_by_clinic()` ほか
- `docs/schema.sql` / `app/db_migrations.py` — schema source of truth と DB 初期化

## 対象経路

画像 OCR 経路（`ImageProcessingService.process`）と既存 OCR JSON 経路（`process_input_json` / `ReceiptProcessingService.process`）のうち、date anchor 判定は構造化 date と clinic/template 情報を必要とするため、**主に画像 OCR 経路（サービス層）で統合**する。`process_input_json` は互換性を保つ。

## スコープ

### 含むもの
- 構造化 date と OCR 日付候補の照合（`parse_date()` 比較）+ template date coords による候補選択
- 選択した date box の左上を offset とした全 box 再正規化（coord_normalizer 拡張）
- date anchor 未学習・一致なし・重複/曖昧・無効 box 時の従来方式へのフォールバック
- template 座標基準の識別と、既存基準 → date 基準への座標変換 + `template_history` への旧値保存
- 変換済み template の二重変換防止（idempotent）
- `docs/schema.sql` と既存 SQLite DB 用の idempotent migration
- raw JSON / DB 保存される OCR box / structured output / template feedback の座標系同期
- 各修正の単体・結合・回帰テスト

### 含まないもの（次回タスク）
- RealLLMClient（非 mock）での anchor 判定の特別対応
- 複数出捐先・自動テンプレート最適化
- ロールバック UI
- 計算（Phase 2）

## 受入条件

1. date 座標が未学習の clinic では従来の座標正規化が維持される。
2. フォーム修正で date 座標が学習された後、同じ clinic/layout の次回処理で候補が信頼できる場合、抽出元 date box を基準に全 OCR box が正規化される。
3. 同じ値の日付が複数ある、日付表現の照合に失敗する、または距離による候補判定が曖昧な場合、誤った候補へ切り替えず従来方式へフォールバックする。
4. テンプレート座標の基準切替は一度だけ実行され、旧座標は `template_history` に残り、既存 correction の近傍検索が新基準で継続する。
5. low-confidence gate と前処理 retry の既存挙動が保たれる。
6. 画像 OCR / `--input-json`、raw JSON / DB OCR data / template feedback で座標系が一貫する。
7. 既存テストと追加した回帰テストが成功する。

## 設計判断

| 項目 | 決定 | 理由 |
|------|------|------|
| date 候補のテキスト照合 | 既存 `parse_date()` で ISO `YYYY-MM-DD` に正規化して比較 | Issue #32 から `normalize_text()` は日付数値に使えず、`parse_date()` を再利用するのが最小変更。表記ゆれ（`2026/01/15` と `2026年1月15日`）を同一形式へ揃える |
| 候補選択の優先順 | テキスト一致（`parse_date` 同値の候補を列挙）→ 複数候補時は template date coords への `search_by_proximity_multi()` 中心距離で絞る | Issue 方針「既存優先関係を尊重」に従い、`coord_search.py` の既存関数を再利用 |
| 曖昧判定の閾値 | **既存値を使用**（proximity `DEFAULT_PROXIMITY_THRESHOLD=50.0`, テキスト類似度 0.6, confidence 0.8） | ユーザー方針「支障が出ない限り既存のまま」。新規に固有閾値を導入しない |
| anchor 一意性条件 | テキスト一致候補がちょうど 1 件、**かつ**（template date box がある場合はその中心に 50px で一意に近接）→ date anchor 採用 | 重複・曖昧・一致なしは従来 way へフォールバック（受入条件 3） |
| 実行タイミング | 「OCR → topmost 正規化 → 構造化 parse(date/clinic) → anchor 解決 → date 基準へ再正規化」の順に統合 | template coords は topmost 基準で保存されるため、まず topmost 基準で構造化 date を得てから anchor を解決する必要がある |
| 座標基準の識別 | `templates` に `coord_basis TEXT NOT NULL DEFAULT 'topmost'` 列を追加（値: `topmost` / `date`） | 専用列で識別子を分離し、`coords_corrections` に sentinel を混ぜない。既存 DB へは idempotent な ALTER で適用 |
| 基準切替時の履歴 | template 更新と同一トランザクションで `template_history`（change_reason=`basis_migration`）に旧 topmost 座標を保存 | 受入条件 4（旧座標を残す + 部分更新防止） |
| 二重変換防止 | `coord_basis` が既に `date` なら再変換しない（guard） | 受入条件 4 / 6 |

---

## 相談事項（実装前に決定を確認）

ユーザー方針に従い閾値は既存値を用いるが、以下はアーキテクチャ上の分岐で、実装前に確認したい。

### Q1. date 基準への再正規化後に構造化 parse を再実行するか
- **実装（確定）**: **再実行しない。** raw を date 基準へ再正規化した後、DB の `receipts.ocr_json` を新基準で更新する（`update_receipt_ocr_json_by_source`）方式を採用。
  - 理由: `process_input_json` は呼び出しごとに新しいレシート行を挿入するため、素直に再実行すると**同じ画像の receipt 行が二重登録**され、`get_receipt_by_source_path` の一意性や修正フローを壊す。
  - 構造化出力（date/clinic/amount）はテキスト抽出に由来し、座標基準に依存しないため、再解析による値の変化はない。DB 保存 box の座標同期（受け入れ条件6）は `ocr_json` 更新で達成できる。
- 影響: `process_input_json` は無変更。画像処理/監視経路で raw 再正規化 + DB `ocr_json` 更新のみ行う。

### Q2. date anchor の「信頼できる」判定に template date coords を必須にするか
- **実装（確定・案A）**: template に date coords がない（未学習）場合は従来方式を維持。テキスト一致が1件でも template date box がなければ anchor を採用しない（受入条件1）。

### Q3. `coord_basis` の導入方法
- **実装（確定・案A）**: `templates` に `coord_basis TEXT NOT NULL DEFAULT 'topmost'` 列を追加。`db_migrations` で `PRAGMA table_info` 確認 → `ALTER TABLE ADD COLUMN` の idempotent 移行。

上記は overview.md 冒頭の「相談事項」に対する確定結果。詳細は実装後の `architecture.md` / `tasks.md` を参照。
