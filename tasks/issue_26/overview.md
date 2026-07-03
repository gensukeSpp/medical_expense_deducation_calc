# Issue #26: 残る4課題の修正 — FastAPI → DB 永続化の課題解決

## 目的

`uv run main.py --serve --db-path data/*.db` で FastAPI Web UI から操作した際に発生する4つの課題を修正する。DB と JSON ファイルの間のデータ不整合、テンプレート学習の未動作、およびコード重複を解消する。

## 参照

- [要件定義書.md](../../要件定義書.md) 「7. DB 設計」「8. Web UI」
- [Issue #24 実装](../../tasks/issue_24/overview.md) — パイプライン自動連鎖 + 座標近接しきい値（20px）
- [Issue #22 実装](../../tasks/issue_22/overview.md) — 座標補正フィードバック
- [Issue #20 実装](../../tasks/issue_20/overview.md) — Web UI + DB 永続化基盤
- `app/normalization.py` — `parse_amount()` のプレーン数字非対応が原因
- `app/services/receipt_service.py` — `update_receipt()` の clinic_id / テンプレート連携不備
- `app/watcher.py` — `parse_args()` 重複

## 4つの課題

| # | 課題 | 優先度 | 原因概要 |
|---|------|--------|---------|
| 1 | JSON の `amount` が null（DB は正しい） | 中 | `parse_amount()` がプレーン数字文字列をパースできない |
| 2 | `receipts` テーブルの `clinic_id` (FK) が NULL | **高** | `update_receipt()` で clinic_id 確定後に UPDATE がない |
| 3 | `templates` テーブルにデータが入らない | **高** | raw_data ファイル名誤り / OCR データ欠落 / 検索方式の誤用 |
| 4 | `watcher.py` と `args.py` の引数定義重複 | 低 | `watcher.py::parse_args()` が独立定義 + model/db_path 未伝播 |

## スコープ

### 含むもの
- `parse_amount()` のプレーン数字文字列対応（"3800", "3,800" → 3800）
- `update_receipt()` での clinic_id UPDATE 追加
- `raw_data_json_path` ファイル名修正（glob 検索で正しいパスを解決）
- OCR データ取得の改善（ファイルからの直接読み込みフォールバック）
- テンプレートフィードバックに座標近接検索（`search_by_proximity_multi`）を使用
- `watcher.py` の引数定義重複解消 + model/db_path 伝播
- 各修正の単体テスト・結合テスト

### 含まないもの（次回タスク）
- RealLLMClient の統合（別 Issue）
- テンプレート座標の自動調整・最適化
- Web UI の拡張（複数一括編集等）
- ロールバック UI

## 受入条件

1. ユーザーが Web UI で `amount` フィールドを修正した後、JSON ファイルに正しい値が保存されること
2. Web UI での修正後、`receipts` テーブルの `clinic_id` が正しい clinic ID で埋まっていること
3. 修正時に座標が検出できた場合、`templates` テーブルに正しいテンプレートレコードが作成されること
4. `watcher.py` を単独実行した場合も、`main.py` 経由の場合も同じ引数体系で動作すること
5. 既存テストが全てパスすること
6. Web UI の修正 → DB 反映 → JSON 更新の一貫性が維持されること

## 設計判断

| 項目 | 決定 | 理由 |
|------|------|------|
| Task1 parse_amount 拡張 | プレーン数字文字列の `int()` 変換を試行 + カンマ除去 | 最小変更で最大効果。`"3800"` → 3800、`"3,800"` → 3800 に対応 |
| Task2 clinic_id 更新 | `add_correction` 実行後、同一トランザクション内で `UPDATE receipts SET clinic_id = ?` を実行 | トランザクション一貫性を維持。既存の `conn` + `with conn:` ブロック内で実行 |
| Task3 raw_data パス解決 | `{file_stem}-raw_data.json` を glob で検索（mtime サフィックスを考慮） | ファイル名に mtime が含まれるため完全一致不可。`glob` + `sort` で最新を取得 |
| Task3 テンプレートFB方式 | **テンプレート座標あり**: `search_by_proximity_multi`（近接検索）<br>**テンプレート座標なし**: `search_coordinates`（文字列類似度） | テンプレート座標が存在する場合は座標近接検索が正確。存在しない場合は従来の文字列検索でフォールバック |
| Task4 引数重複 | `watcher.py::parse_args()` を削除し `args.setup_args()` に統一 | 単一責任の原則。`main.py` が既に `setup_args()` を使用 |
