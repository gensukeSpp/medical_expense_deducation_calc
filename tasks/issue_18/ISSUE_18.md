# Issue 18 (local): 抜き出したデータと座標をDBに記録する（SQLite）

目的
- 抽出済みの領収書データ（ラベル／値／正規化結果）とOCRの座標情報を永続化し、テンプレート管理とユーザー修正のフィードバック基盤を整備する。

受入条件
- SQLite を用いたスキーマ（receipts, clinics, templates, corrections, users）をリポジトリに追加する。
- receipts テーブルは最低限以下を含む:
  - id (PK, UUID), source_path (TEXT), ocr_json (JSON), normalized_json (JSON), clinic_id (FK nullable), created_at (TIMESTAMP)
- templates テーブル:
  - id, clinic_id, version, coords_corrections (JSON), created_at
- corrections テーブル:
  - id, receipt_id, field_name, old_value, new_value, user_id, created_at
- マイグレーション/初期スキーマ作成スクリプトを提供する（例: app/db_migrations.py または scripts/init_db.py）。
- app/db.py に簡易 CRUD API を追加（connect, insert_receipt, get_receipt, upsert_template, add_correction など）。
- structural_parser が抽出結果を書き込める統合ポイントを追加し、オプションで既存の result.json 出力も継続可能。
- エラー時は構造化ログに記録し、処理は継続する（例: app/error_logging.py にエントリ）。
- ユニットテストを追加（スキーマ作成、基本CRUD、corrections ロジック）。

設計メモ
- DB 標準: SQLite (ファイル: data/db.sqlite3)
- ORM/軽量ラッパー: まずは sqlite3 標準ライブラリ + simple helper を採用。将来 SQLAlchemy へ移行可能な抽象層を作る。
- トランザクション: 複数テーブル更新はトランザクションを使う。
- JSON カラム: ocr_json, normalized_json, coords_corrections は TEXT に JSON dump で格納。

実装タスク（推奨順）
1. docs/schema.sql または scripts/init_db.py を追加（テーブル定義 SQL）。
2. app/db.py を作成（接続管理、CRUD 関数）。
3. app/db_migrations.py (軽量) を作成し、初回セットアップ用 CLI を提供（例: python -m app.db_migrations init）。
4. structural_parser.py に DB 書込呼び出しを追加（オプションで file output を残す）。
5. tests/test_db.py を追加（pytest、tmp_path を使った一時DB 上での検証）。
6. README の DB セクションを更新（バックアップ / データ移行の注意）。

テスト計画
- unit:
  - schema creation: scripts/init_db.py によりテーブルが作成されること
  - insert_receipt / get_receipt: roundtrip 検証
  - add_correction: corrections レコードが作成され、receipt の normalized_json が更新されるケース
- integration:
  - structural_parser が OCR JSON を正常に receipt レコードとして保存すること

CI / 開発フロー
- テストはローカルで sqlite3 を利用して実行できるため CI 変更は不要。ただし、テストでデータベースファイルが作られるパスは tmpdir を使う。

関連ファイル（編集候補）
- 新規: app/db.py, scripts/init_db.py, docs/schema.sql, tests/test_db.py
- 変更: app/structural_parser.py（DB 書込統合ポイントを追加）、main.py（オプションで DB 書込を有効化するフラグ）、app/error_logging.py（DB 書込失敗時のログ）

次のアクション
- この ISSUE_18.md のレビュー後、ブランチを切って実装を開始する（推奨ブランチ名: feature/issue-18-db-persistence）。

作成日時: 2026-06-18T17:40:38+09:00
