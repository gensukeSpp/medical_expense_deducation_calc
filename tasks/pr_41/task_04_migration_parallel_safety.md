# タスク 04: SQLite migration の並列初期化安全化

## 課題概要

[P2] SQLite migrationが別々の接続で実行され、並列初期化時の競合に弱い

## 目的

watcher/CLI等が初回に並行してDB初期化する構成でも、migration処理が起動失敗しないようにする。migrationを一つの接続・排他トランザクションで実施し、SQLiteのwrite lock取得後に列有無を確認することで、duplicate columnエラーを防止する。

## 計画

1. `app/db_migrations.py` の `run_migrations()` 関数を修正し、schema適用とcoord_basis列追加を一つの接続・排他トランザクションで実施
2. SQLiteのwrite lock取得後に列有無を確認するロジックを追加
3. duplicate-column raceを安全に再確認するテストを追加

## タスク

- [ ] `app/db_migrations.py:run_migrations()` 関数を修正
- [ ] schema適用（`executescript()`）とcoord_basis列追加を一つの接続内で実行
- [ ] `BEGIN EXCLUSIVE TRANSACTION` で排他トランザクションを開始
- [ ] 列有無を `PRAGMA table_info(templates)` で確認
- [ ] 列がない場合のみ `ALTER TABLE templates ADD COLUMN coord_basis TEXT NOT NULL DEFAULT 'topmost'` を実行
- [ ] `COMMIT` でトランザクション終了
- [ ] テスト追加: 複数プロセスが同時初期化する競合ケースをシミュレートするテスト
- [ ] テスト実行: `pytest tests/test_migrations.py -v`

## 実装方針

```python
# app/db_migrations.py: run_migrations() の修正
# 変更前:
# conn = get_db_connection(db_path)
# try:
#     conn.executescript(schema_sql)
# finally:
#     conn.close()
#
# conn = get_db_connection(db_path)
# try:
#     with conn:
#         _add_coord_basis_column_if_missing(conn)
# finally:
#     conn.close()
#
# 変更後:
# conn = get_db_connection(db_path)
# try:
#     conn.executescript(schema_sql)
#     # 一つの接続・排他トランザクションで migration を実施
#     conn.execute("BEGIN EXCLUSIVE TRANSACTION")
#     try:
#         cols = {row["name"] for row in conn.execute("PRAGMA table_info(templates)")}
#         if "coord_basis" not in cols:
#             conn.execute(
#                 "ALTER TABLE templates ADD COLUMN coord_basis TEXT NOT NULL DEFAULT 'topmost'"
#             )
#     except Exception:
#         conn.rollback()
#         raise
#     else:
#         conn.commit()
# finally:
#     conn.close()
```

## 影響範囲

- `app/db_migrations.py`: `run_migrations()` 関数
- `tests/test_migrations.py`: 並列初期化テスト追加

## 検証方法

- 単一プロセスでのmigration動作を確認
- 複数プロセスが同時初期化する競合ケースをシミュレートするテストで、duplicate columnエラーが発生しないことを検証
- 既存テスト `tests/test_migrations.py` 全テストパス確認
