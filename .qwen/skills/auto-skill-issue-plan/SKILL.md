---
name: issue-plan
description: アーキテクチャスナップショットと既存タスクテンプレートからIssue実装計画を立案する手順
source: auto-skill
extracted_at: '2026-06-29T05:16:12.154Z'
---

# Issue 実装計画の立案手順

## 目的

既存のアーキテクチャ文書とコードベースを元に、GitHub Issue の実装計画を体系的に作成する。

## 手順

### 1. アーキテクチャの進捗把握

- `docs/architecture/README.md` を読み、最新のスナップショットから現在のプロジェクト状態を理解する
- 各スナップショットの「Next steps / improvements」セクションを確認し、未完了項目を特定する
- 同一期間の複数スナップショットがある場合、最新のものを優先

### 2. Issue 内容の取得

- `gh issue view <number>` で Issue の詳細（本文、ラベル、マイルストーン）を取得
- gh CLI が利用不可の場合、`gh issue list --json number,title` で存在確認した上でユーザーに問い合わせる
- Issue 内の参照（要件定義書.md の特定セクション、過去Issueの成果物など）を辿る
- **受入条件（Acceptance Criteria）を抽出**し、テストケースと1対1でマッピングできるようにしておく

### 3. コードベース調査 — 並列探索

以下の観点で既存コードを探索。複数ファイルを並行して読むことで効率化する:

- **データ構造**: 出力JSONのスキーマ（例: `structured_output_schema.json`）、DBスキーマ（`docs/schema.sql`）
- **既存CRUD**: `app/db.py` の全関数一覧、既存テスト（`tests/test_db.py`）
- **再利用可能ユーティリティ**: `app/output.py`（write_json_atomic）、`app/input.py`（read_json）、`app/error_logging.py`（append_error）、`app/normalization.py`（parse_amount, parse_date）
- **前回Issueのタスク管理形式**: `tasks/issue_<N>/` のファイル構成を直接読み、フォーマットを継承する（overview.md, architecture.md, tasks.md, test_plan.md の4ファイル構成）
- **依存関係**: `pyproject.toml` の dependencies
- **CLIエントリポイント**: `main.py` + `app/args.py` の引数定義
- **重要**: `git log --oneline -10` で現在のブランチと最新コミットを確認し、どの機能がマージ済みかを把握する

### 4. 設計判断のユーザー確認ループ

Issue 内に「もし〜なら見送って構いません」などの条件付きスコープや、数値しきい値（px, %, etc.）に関する設計判断がある場合、**計画を確定する前にユーザーに確認する**:

- 選択肢を提示（推奨案 + 代替案）
- 各選択肢のトレードオフを簡潔に説明
- ユーザーの回答を待ってから設計を確定する

確認すべき典型パターン:
- 条件付きスコープ（「RealLLMClient が包括できるなら不要」→ Mockのみ？両方？）
- 数値しきい値（デフォルト20px？10px？30px？）
- 統合箇所（既存関数内 vs 別ステップ）
- 技術選定のトレードオフ

### 5. 設計方針の策定

- 要件定義書（`要件定義書.md`）の該当セクションを参照し、スコープを確認
- 「含むもの」「含まないもの」を明確に区分（次回タスクと線引き）
- 技術選定の理由を記載（採用技術 + 代替案の検討結果）
- 既存コードの再利用箇所を明記（モジュール名・関数名）
- 設計判断表を作成（項目 / 決定 / 理由）

### 6. 計画文書の作成

`tasks/issue_<N>/` 配下に以下の4ファイルを作成。前回Issueのファイル構成を継承する:

| ファイル | 内容 |
|---------|------|
| `overview.md` | 目的、スコープ（含む/含まない）、受入条件、設計判断表 |
| `architecture.md` | システム構成図（Mermaid）、データフロー、ルーティング、エラーハンドリング、モジュール構成（変更/変更なしの一覧） |
| `tasks.md` | 実装タスクの詳細一覧（優先順位・依存関係グラフ・ファイル変更リスト・推奨実装順序） |
| `test_plan.md` | テスト戦略、フィクスチャ設計、テストケース一覧表（ID・概要・確認点）、エッジケース一覧 |

### 7. 実装タスクの粒度ガイドライン

- 1タスクは原則1ファイルの変更に集約（大規模な場合はサブタスクに分割: 1-A, 1-B, ...）
- 依存関係をMermaid graphで可視化
- 実装順序（推奨）を明示
- 各タスクに「新規ファイル」「変更ファイル」を明記
- タスク番号と変更ファイルが1対1対応することを推奨（`1-A: watcher.py`、`1-B: processor.py` 等）

### 8. テスト計画のポイント

- 利用するテストフレームワーク・フィクスチャを既存テストから継承（`test_db.py` の `temp_db` パターン等）
- テスト対象コードは依存性注入可能な設計にし、fixtureで差し替え可能にする
- テストケースは以下を網羅:
  - 正常系（Happy path）
  - 異常系（ファイル不存在、DB未初期化等）
  - エッジケース（null値、空配列、不正フォーマット等）
  - htmx等の部分更新がある場合、レスポンスのHTML断片検証
- 受入条件の各項目を1つ以上のテストケースでカバーする（トレーサビリティ確保）

### 9. 計画の決定と保存

- ユーザーに `exit_plan_mode` で計画を提示し、承認を得る
- 承認後、`tasks/issue_<N>/` に4ファイルを作成する
- `todo_write` で進捗を可視化しながら作業する

## 実装時の注意点（経験則）

### 既存コードとのデータ整合性ギャップ

- `server.py` が `file_stem` をレシートIDとして使う一方、`structural_parser.py` はUUIDで保存する場合がある。この乖離はテストでは発見しづらいので必ず確認する。
- **対策**: `get_receipt_by_source_path()` など、複数の検索キーでレコードを特定できる関数を事前に追加する。

### DB外部キー制約の挿入順序

- 外部キー制約があるテーブルに履歴レコードを挿入する場合、**参照先レコードを先にINSERT**してから履歴を挿入しないと `IntegrityError` になる。
- **対策**: `upsert_template → insert_template_history` の順で実行する。

### テキスト類似度検索の現実的なしきい値

- `difflib.SequenceMatcher` の類似度比は、日本語漢字+スペースの組み合わせでは直感より低く出ることがある（例: `"山田 太郎"` vs `"山田花子"` → 約0.44）。
- **対策**: デフォルトしきい値を0.7に設定し、テストでは実データに合わせて調整する。類似度の計算結果を確認するテストを先に書くと安心。

### 段階的な機能追加（Graceful Degradation）

- 追加機能（例: 座標フィードバック）は既存の `try/except` ブロックの内側に追加し、失敗しても既存の修正処理が継続する設計にする。
- **対策**: 新規ロジック全体を内側の `try/except` で囲み、エラーは `append_error()` でログに残す。このパターンでテストに失敗しても既存テストには影響しない。

### HTML エラーページの戻り値
- 部分的な失敗（一部フィールドの座標未検出など）の場合、エラーHTMLを返しつつ更新データを含めることで、ユーザーが修正内容を確認できる。
- **対策**: テンプレートに `coord_errors` と `updated_data` の両方を渡す。

### black フォーマットのターゲットバージョン
- 最新の black (26.x) はデフォルトで Python 3.15 をターゲットにするため、Python 3.11 プロジェクトでは `black --target-version py311 .` を指定しないと syntax check に失敗する。
- **対策**: `pyproject.toml` に `[tool.black] target-version = ['py311']` を設定するか、CLIフラグで指定する。

### パイプライン自動連鎖（Auto-chaining）
- OCR → 構造化抽出のように、ステップ1の完了ファイルを入力としてステップ2を自動実行する連鎖は、**各ステップの関数を前ステップの成功直後に呼び出すだけ**で実現できる。
- **実装パターン**:
  ```python
  # ステップ1: OCR (raw_data生成)
  structured = process_image(image_path, output_json_path=output_json_path, ocr=ocr)
  # ステップ2: 構造化抽出 (成功すれば即座に実行)
  try:
      process_input_json(output_json_path, model=model, output_dir=output_dir, db_path=db_path)
  except Exception:
      LOG.exception("Failed to generate structured data")
  ```
- **注意点**:
  - ステップ2の失敗はステップ1の成功を無効にしない — エラーはログに記録し処理継続
  - 関数シグネチャに `model` / `db_path` などのパラメータを追加伝播する必要がある場合、デフォルト値を設定して既存呼び出し元を壊さないようにする（例: `model: str = "mock"`）
  - テストのファイル数アサーションは連鎖後も更新する（`*-raw_data.json` + `*-structured_data.json` の2ファイルになる）

### 文字列類似度検索に座標近接検索を追加するパターン
- 既存の文字列類似度（difflib.SequenceMatcher）とは**別の次元の検索**であり、独立した関数として追加する。
- **新規追加が必要なもの**:
  - ヘルパー: `_calculate_box_center(box)` / `_euclidean_distance(p1, p2)` — 幾何計算
  - 検索関数: `search_by_proximity(ocr_entries, target_box, threshold=20.0)` — 中心点間距離で最寄りエントリを返す
  - 複数フィールド版: `search_by_proximity_multi(ocr_entries, field_box_map, threshold)` — 一括検索
- **プロキシミティと他の手法の使い分け**:
  - 文字列類似度（difflib）: ユーザー修正時のold_value検索向け。値が変わってもテキストは似ている
  - 座標近接（Euclidean distance）: テンプレート座標からの抽出向け。撮影ズレを許容するが値そのものはテキストで取得
  - 近接検索の戻り値はOCRエントリ全体（`{text, confidence, box}`）— テキスト値と座標の両方を後続処理で使える

### 既存抽出パイプラインへのテンプレート連携パターン
- 既存の `process_input_json()` 内で、**抽出 → テンプレート連携 → 正規化 → 出力** の順で挿入する。
- **条件ゲート**:
  ```python
  if model == "mock" and db_path and extracted.get("clinic"):
      # MockLLMClient 時のみテンプレートによる上書き実行
  ```
  - model指定でゲートすることで、RealLLMClientでは座標近接を使わない（LLMへの干渉防止）
  - `db_path` が設定されていなければスキップ（DB未接続でも動作する設計）
  - clinic未検出ならスキップ（クリニック未特定の領収書ではテンプレート連携不可）
- **上書きルール**: テンプレート座標にマッチしたフィールドのみ抽出値を上書き。マッチしないフィールドは従来のMockLLMClient抽出値を維持
- **エラーハンドリング**: テンプレート連携全体を内側の `try/except` で保護。失敗時は `append_error()` で記録し、従来フローにフォールバック

### upstream データ形式の不整合対応
- パイプライン連鎖時に、前ステップの出力形式と次ステップの入力期待形式が異なる場合がある（例: OCRパイプラインは `[{text, confidence, box}]` 形式のリストを出力するが、MockLLMClientは `{"text_lines": [...]}` 形式のdictを期待）
- **対策**: データの生産元（OCRパイプライン）を変更せず、消費側（MockLLMClient）で両形式に対応する。これにより既存の単体テストや他パス（`--input-json`）への影響をゼロにする。
  ```python
  def normalize_lines(ocr_json):
      if isinstance(ocr_json, list):
          return [entry.get("text", "") for entry in ocr_json if entry.get("text")]
      # dict形式の従来処理
      ...
  ```

### 外部ツール（parse_amount等）の入力形式制約
- `parse_amount()` は `"3,800"` ではなく `"3,800円"` など「アノテーション付き」の文字列を期待している。テストデータを作る際は、実際のOCR出力に近い形式（金額なら `"3,800円"`、日付なら `"2026/01/15"`）を用いる。さもないと `None` が返り、テストが意図通りに動かない。

### テストデータでの glob パターン注意
- watcher が出力するファイル名は `{stem}_{mtime}-raw_data.json`（ハイフン + `raw_data`）。テストの glob パターンで `*_raw_data.json`（アンダースコア）と書くとマッチしない。`*-raw_data.json` が正しい。