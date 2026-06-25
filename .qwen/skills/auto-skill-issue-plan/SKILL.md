---
name: issue-plan
description: アーキテクチャスナップショットと既存タスクテンプレートからIssue実装計画を立案する手順
source: auto-skill
extracted_at: '2026-06-23T04:14:18.473Z'
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

- `gh issue view <number> --json title,body,labels` で Issue の詳細を取得
- gh CLI が利用不可の場合、`gh issue list --json number,title` で存在確認した上でユーザーに問い合わせる
- Issue 内の参照（要件定義書.md の特定セクション、過去Issueの成果物など）を辿る

### 3. コードベース調査

以下の観点で既存コードを探索:

- **データ構造**: 出力JSONのスキーマ（例: `structured_output_schema.json`）、DBスキーマ（`docs/schema.sql`）
- **既存CRUD**: `app/db.py` の全関数一覧、既存テスト（`tests/test_db.py`）
- **再利用可能ユーティリティ**: `app/output.py`（write_json_atomic）、`app/input.py`（read_json）、`app/error_logging.py`（append_error）、`app/normalization.py`（parse_amount, parse_date）
- **前回Issueのタスク管理形式**: `tasks/issue_<N>/` のファイル構成（overview.md, subtasks_index.md, 番号付きtaskファイル等）
- **依存関係**: `pyproject.toml` の dependencies
- **CLIエントリポイント**: `main.py` + `app/args.py` の引数定義

### 4. 設計方針の策定

- 要件定義書（`要件定義書.md`）の該当セクションを参照し、スコープを確認
- 「含むもの」「含まないもの」を明確に区分（次回タスクと線引き）
- 技術選定の理由を記載（採用技術 + 代替案の検討結果）
- 既存コードの再利用箇所を明記（モジュール名・関数名）

### 5. 計画文書の作成

`tasks/issue_<N>/` 配下に以下の文書を作成。ファイルは4つに分割:

| ファイル | 内容 |
|---------|------|
| `overview.md` | 目的、スコープ（含む/含まない）、受入条件、技術選定 |
| `architecture.md` | システム構成図（Mermaid）、データフロー、ルーティング、既存コード再利用箇所の一覧表 |
| `tasks.md` | 実装タスクの詳細一覧（優先順位・依存関係・ファイル変更リスト含む） |
| `test_plan.md` | テスト戦略、フィクスチャ設計、テストケース一覧表（ID・概要・確認点）、エッジケース |

### 6. 実装タスクの粒度ガイドライン

- 1タスクは原則1ファイルの変更に集約（大規模な場合はサブタスク分割）
- 依存関係をMermaid graphで可視化
- 実装順序（推奨）を明示
- 各タスクに「新規ファイル」「変更ファイル」を明記

### 7. テスト計画のポイント

- 利用するテストフレームワーク・フィクスチャを既存テストから継承（`test_db.py` の `temp_db` パターン等）
- テスト対象コードは依存性注入可能な設計にし、fixtureで差し替え可能にする
- テストケースは以下を網羅:
  - 正常系（Happy path）
  - 異常系（ファイル不存在、DB未初期化等）
  - エッジケース（null値、空配列、不正フォーマット等）
  - htmx等の部分更新がある場合、レスポンスのHTML断片検証