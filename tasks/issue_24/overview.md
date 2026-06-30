# Issue #24: 抽出までの一連の動作と、座標におけるしきい値

## 目的

2つのタスクを実装する:

1. **一連の動作への組み込み**: 領収書画像投入 → OCR（`*-raw_data.json`）→ 必要データ抽出（`*-structured_data.json`）までのパイプラインを完成させる。
2. **座標におけるしきい値の設定**: クリニックテンプレートの座標情報を活用し、OCR 前の撮影ズレを考慮した許容範囲（近接しきい値）を導入する。

## 参照

- [要件定義書.md](../../要件定義書.md) 「5. ロジックフロー: 1, 2」「6. 実装ステップ: ステップ2, 3, 4」
- [Issue #22 実装](../../tasks/issue_22/overview.md) — 座標補正フィードバック（文字列類似度しきい値 0.7）
- [Issue #20 実装](../../tasks/issue_20/overview.md) — Web UI + DB 永続化基盤
- `app/coord_search.py` — `difflib.SequenceMatcher` による文字列類似度検索（既存）
- `app/structural_parser.py` — `process_input_json()` OCR JSON → 構造化データ抽出

## スコープ

### 含むもの
- watcher モードでの OCR → 構造化抽出の自動連鎖
- single-image モード（`--image-name`）での OCR → 構造化抽出の自動連鎖
- `coord_search.py` への座標近接検索関数追加
- `structural_parser.py` でのテンプレート連携（MockLLMClient 時のみ）
- 座標近接しきい値デフォルト 20px
- 単体テスト・結合テスト

### 含まないもの（次回タスク）
- RealLLMClient での座標近接利用（LLM が包括的に処理するため本タスクでは未使用）
- テンプレート座標の自動調整・最適化（固定しきい値のみ）
- ロールバック UI

## 受入条件

1. 画像投入 → OCR → 構造化データ（`*-structured_data.json`）までが自動生成されること
2. 同一クリニック名のテンプレートが DB に存在する場合、座標近接しきい値内の OCR テキストが抽出に利用されること
3. テンプレートが存在しない場合、従来の MockLLMClient 抽出が行われること
4. テンプレート連携失敗時はエラーログに記録され、通常抽出が継続すること
5. 既存テスト（`test_coord_search.py`, `test_feedback.py`, `test_web.py`, `test_watcher_integration.py`）が全てパスすること

## 設計判断

| 項目 | 決定 | 理由 |
|------|------|------|
| Task1 統合方式 | `process_one()` / `process_single_image()` 内で `process_input_json()` を呼ぶ | 最小変更でパイプライン完成、既存の `--input-json` CLI パスをそのまま活用 |
| watcher パラメータ | `process_one()` に `model` / `db_path` を追加伝播 | args からの伝播を明示的にし、テスト時の注入を容易にする |
| Task2 スコープ | MockLLMClient 時のみ有効 | RealLLMClient では LLM が包括的に処理するため妨げにならない設計 |
| 近接しきい値 | 20px（box中心点間のユークリッド距離） | 標準的な撮影ズレを許容、誤検出とのバランス |
| テンプレート優先度 | MockLLMClient 抽出結果を上書き | テンプレート情報が最も確実な抽出手段（過去のユーザー修正で学習済み） |
| 統合箇所 | `process_input_json()` 内の後処理段階 | クリニック名確定後（MockLLMClient 抽出後）にテンプレート検索・上書きを行う |
