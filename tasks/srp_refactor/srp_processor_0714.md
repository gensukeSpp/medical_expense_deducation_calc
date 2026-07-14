# SRP Refactoring Task: `app/processor.py`

## 概要
`.gemini/reviews/srp-review-processor-20260714.md` のレビューに基づき、`app/processor.py` の `process_single_image` 関数における単一責任の原則 (SRP) 違反を解消するためのリファクタリングを実施する。

## 目標
- `app/processor.py` を純粋なオーケストレーターへと変更する。
- ビジネスロジックを `ImageProcessingService` クラスに集約する。
- CLI制御（`argparse`, `sys.exit`）とビジネスロジックを分離する。
- 各ステップ（OCR, 正規化, 解析）を依存注入されたサービスに委譲する。
- `low_confidence` フラグの付与ロジックを適切な場所に分離する。

## 実装タスク

### 1. 現状分析と設計
- [ ] `app/processor.py` の現在の実装詳細を完全に把握する。
- [ ] `ImageProcessingService` のインターフェース（メソッド、引数、戻り値）を詳細に設計する。
- [ ] 依存関係（OCRエンジン、DBリポジトリ、正規化サービス、解析サービス）の整理。

### 2. `ImageProcessingService` の実装
- [ ] `app/services/image_processing_service.py` (または適切な場所) に `ImageProcessingService` クラスを作成する。
- [ ] OCR、正規化、構造解析の各ステップを呼び出すオーケストレーションロジックを実装する。
- [ ] `low_confidence` フラグの処理を、レビューの推奨に従い適切なサービス（`structural_parser` または新設の `ReceiptAugmentor`）へ分離する。

### 3. `app/processor.py` のリファクタリング
- [ ] `process_single_image` を `ImageProcessingService` を利用する形に書き換える。
- [ ] CLI特有の処理（引数解析、エラー時の `sys.exit`）を `app/processor.py` または `main.py` の適切なレイヤーに分離する。
- [ ] `app/processor.py` から直接的なファイルシステム操作や複雑なバリデーションを排除する。

### 4. 検証
- [ ] リファクタリング後の `app/processor.py` が正しく動作することを確認する（既存のCLI経由での実行テスト）。
- [ ] `ImageProcessingService` に対する単体テストを作成・実行する。
- [ ] 既存の統合テストが壊れていないことを確認する。
