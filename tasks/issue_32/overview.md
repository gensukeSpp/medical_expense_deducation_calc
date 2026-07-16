# Issue #32: 相対距離から座標値を取り直す

## 目的

OCR 後の絶対座標を相対座標に変換し、同一クリニックのレシート間での撮影ズレ・余白による座標バラつきを吸収する。併せて近接値しきい値を 50px に引き上げ、低信頼度 OCR 時はテンプレート更新を抑止する。

## 参照

- [要件定義書.md](../../要件定義書.md)
- [Issue #24 実装](../../tasks/issue_24/overview.md) — パイプライン自動連鎖 + 座標近接しきい値（20px）
- [Issue #26 実装](../../tasks/issue_26/overview.md) — テンプレートフィードバック改善
- `app/ocr_pipeline.py` — `process_image()` OCR 実行
- `app/watcher.py` — `process_one()` パイプライン連鎖
- `app/processor.py` — `process_single_image()` 単一画像処理
- `app/structural_parser.py` — `DEFAULT_PROXIMITY_THRESHOLD` 定義
- `app/services/receipt_service.py` — `get_all_receipts()` 一覧表示
- `app/services/receipt_updater.py` — `update_receipt()` 修正フロー
- `app/web/templates/index.html` — 一覧ページテンプレート

## スコープ

### 含むもの
- 座標相対化関数 `normalize_coordinates()` の新規作成
- watcher / processor パイプラインへの座標相対化ステップ統合
- 最上部要素 confidence < 0.8 時の相対化スキップ + low_confidence フラグ
- 一覧ページでの low_confidence 警告表示
- 修正時、low_confidence レシートのテンプレート更新抑止
- 近接値しきい値 20px → 50px への変更
- 各修正の単体テスト・結合テスト

### 含まないもの（次回タスク）
- RealLLMClient の統合（別 Issue）
- テンプレート座標の自動調整・最適化
- 複数クリニック間の座標比較
- ロールバック UI

## 受入条件

1. OCR 処理後、raw_data.json の全 box 座標が相対座標（最上部 y=0、最左部 x=0）に変換されていること
2. 最上部要素の confidence < 0.8 の場合、座標相対化がスキップされ、structured_data.json に `low_confidence: true` が設定されること
3. 一覧ページで low_confidence なレシートのリンク右に警告が表示されること
4. low_confidence なレシートを Web UI で修正した場合、corrections テーブルには反映されるが templates テーブルは更新されないこと
5. 近接値しきい値が 50px に変更されていること
6. 既存テストが全てパスすること

## 設計判断

| 項目 | 決定 | 理由 |
|------|------|------|
| 座標計算タイミング | raw_data.json 出力後に上書き | `process_image()` 不変、独立テスト容易 |
| 近接値しきい値 | **50px** | サンプル分析で相対化後も最大63pxの残差。50px + 文字列類似度フォールバックでカバー |
| 警告表示位置 | 一覧の各リンク右 | ユーザー確認済み |
| low_confidence 永続化 | structured_data.json にフラグ追加 | Web UI が直接参照可能 |
| テンプレートゲーティング | `ReceiptUpdater` で low_confidence 時は座標フィードバック全体をスキップ | 最小変更で最大効果。既存の修正フローに影響なし |