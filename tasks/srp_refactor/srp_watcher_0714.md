# SRP Refactoring Task: `app/watcher.py`

## 概要
`.gemini/reviews/srp-review-watcher-20260714.md` のレビューに基づき、`app/watcher.py` の単一責任の原則 (SRP) 違反を解消するためのリファクタリングを実施する。

## 目標
`app/watcher.py` に混在している「監視」「ファイル選定・安定性チェック」「OCR処理オーケストレーション」「ファイルシステム操作」「例外・リトライ制御」「CLI構築」の責務を分離し、保守性とテスト容易性を向上させる。

## 実装タスク

### 1. 責務の分離と新クラスの設計・実装
- [ ] **監視層 (`FileMonitor`) の抽出**
    - 監視メカニズム (Polling/Watchdog) を抽象化する。
    - 新しいファイルが検出された際にイベントを発行する仕組みを実装する。
- [ ] **処理層 (`ReceiptProcessor`) の抽出**
    - `app/watcher.py` の `process_one` に相当するロジックをクラス化する。
    - OCR、正規化、解析処理の各コンポーネントを DI (Dependency Injection) で受け取るようにする。
- [ ] **永続化・ファイル管理層 (`FileRepository`) の抽出**
    - ファイルの移動、退避、クリーンアップ、安定性チェック (`is_file_stable`) などの責務を集約する。

### 2. `app/watcher.py` のリファクタリング
- [ ] 既存の `app/watcher.py` からビジネスロジックを削除し、新設したクラスを利用する形に書き換える。
- [ ] 監視と処理をイベント駆動（またはコールバック）で連携させる。

### 3. 依存関係の整理と DI の適用
- [ ] `ReceiptProcessor` が直接 `shutil` や `os` を呼ばず、`FileRepository` を介して操作するように変更する。
- [ ] 各コンポーネントの依存関係を整理し、テスト時にモック化しやすい構造にする。

### 4. 検証
- [ ] リファクタリング後の動作が、既存の機能（ファイル監視からOCR処理完了まで）を損なっていないことを確認する。
- [ ] 既存のテスト (`tests/test_watcher_integration.py` 等) を実行し、パスすることを確認する。
- [ ] 必要に応じて、新しい責務に基づいた単体テストを追加する。

## 参照
- レビュー結果: `.gemini/reviews/srp-review-watcher-20260714.md`
