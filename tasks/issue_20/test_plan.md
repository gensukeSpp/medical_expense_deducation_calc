# Issue #20: テスト計画

## テスト戦略

- **フレームワーク**: pytest + FastAPI TestClient
- **DB**: `tmp_path` フィクスチャで一時 SQLite DB を作成（既存 `test_db.py` のパターンを踏襲）
- **JSONファイル**: `tmp_path` 配下の一時 `output_json/` ディレクトリにモック JSON を配置
- **app/web/server.py** は `output_dir` と `db_path` を引数で受け取れる設計にし、テスト時に差し替え可能にする

## テスト用フィクスチャ

```python
@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """一時的な output_json/ ディレクトリを作成し、
    モック structured_data JSON ファイルを配置する。"""
    out_dir = tmp_path / "output_json"
    out_dir.mkdir()
    # 正常ケース用ファイル
    data = {"name": "山田 太郎", "clinic": "あおばクリニック", "amount": 3800, "date": "2026-01-15"}
    write_json_atomic(out_dir / "receipt-001-structured_data.json", data)
    # clinic null ケース
    data2 = {"name": "花子", "clinic": None, "amount": 1200, "date": "2026-02-20"}
    write_json_atomic(out_dir / "receipt-002-structured_data.json", data2)
    return out_dir

@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """スキーマ適用済みの一時 DB ファイル。"""
    db_file = tmp_path / "test_db.sqlite3"
    run_migrations(db_file, SCHEMA_PATH)
    return db_file

@pytest.fixture
def client(temp_output_dir, temp_db):
    """TestClient インスタンス。server.py に output_dir, db_path を注入。"""
    from app.web.server import create_app
    app = create_app(output_dir=str(temp_output_dir), db_path=str(temp_db))
    with TestClient(app) as c:
        yield c
```

## テストケース一覧

### TC-01: トップページ一覧表示

| 項目 | 内容 |
|------|------|
| テスト名 | `test_index_lists_structured_files` |
| 概要 | `GET /` が正常に一覧を表示する |
| 確認点 | ステータス200 / HTMLに「あおばクリニック-2026-01-15」が含まれる / 2ファイルとも表示される |

### TC-02: clinic null のファイル表示

| 項目 | 内容 |
|------|------|
| テスト名 | `test_index_fallback_display_name` |
| 概要 | clinic が null の場合、ファイル名が表示名として使われる |
| 確認点 | HTMLに `receipt-002` が含まれる |

### TC-03: 空のディレクトリ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_index_empty_directory` |
| 概要 | JSONファイルがない場合、「データがありません」等のメッセージが表示される |
| 確認点 | 空状態の表示を確認 |

### TC-04: 詳細ページ表示

| 項目 | 内容 |
|------|------|
| テスト名 | `test_detail_shows_fields` |
| 概要 | `GET /receipt-001` が正常に詳細を表示する |
| 確認点 | ステータス200 / ラベル「氏名」「クリニック名(調剤薬局名)」「支払い金額」「発行日」が全て含まれる / 値「山田 太郎」「あおばクリニック」「3800」「2026-01-15」が含まれる |

### TC-05: 存在しないファイルの詳細

| 項目 | 内容 |
|------|------|
| テスト名 | `test_detail_not_found` |
| 概要 | 存在しない file_stem の場合 404 を返す |
| 確認点 | ステータス404 |

### TC-06: 修正処理（DBあり）

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_updates_db_and_json` |
| 概要 | `PUT /receipt-001` で修正後、DBとJSONの両方が更新される |
| 手順 | 1. `PUT /receipt-001` を `name=山田 花子` で実行<br/>2. DB の `corrections` テーブルにレコードが追加されたことを確認<br/>3. DB の `receipts.normalized_json` が更新されたことを確認<br/>4. JSON ファイルを再読み込みし、`name` が `山田 花子` になっていることを確認 |
| 確認点 | ステータス200 / htmx応答に更新後の値が含まれる / DB反映 / JSON反映 |

### TC-07: 修正処理（DBなし）

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_updates_json_only` |
| 概要 | `db_path=None` の場合、JSONファイルのみ更新されDBエラーは発生しない |
| 確認点 | JSONファイル更新 / DBエラーでクラッシュしない |

### TC-08: 複数フィールドの修正

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_multiple_fields` |
| 概要 | 一度のリクエストで複数フィールド（例: amount + date）を修正する |
| 確認点 | 全フィールドが正しく更新される |

### TC-09: 金額と日付の正規化

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_normalization` |
| 概要 | 金額 `3,800円` や日付 `2026/01/15` など元のフォーマットで入力されても正規化される |
| 確認点 | 金額は整数、日付は ISO YYYY-MM-DD に正規化されて保存される |

### TC-10: エラー時も修正処理が中断しない

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_db_error_continues` |
| 概要 | DB が利用不可（テーブルなし等）でも JSON ファイル更新は継続され、エラーログに記録される |
| 確認点 | JSONファイル更新 / クラッシュしない / errors.log にエラー記録 |

## テスト実行方法

```bash
# 全テスト実行
pytest tests/test_web.py -v

# 特定テストのみ
pytest tests/test_web.py::test_correction_updates_db_and_json -v

# coverage 確認（オプション）
pytest tests/test_web.py -v --cov=app.web
```

## エッジケース一覧

| ケース | 対応方針 |
|--------|---------|
| JSONファイルが不正フォーマット | スキップ + エラーログ、一覧に表示しない |
| DBファイルが存在しない | `get_db_connection` が自動生成するため問題なし |
| 同時修正（競合） | `add_correction` の `old_value` 検証で競合検出 |
| 金額が数値でない文字列 | `normalize_extracted` で正規化 |
| 日付が空文字 | None として保存、表示は「未設定」等 |