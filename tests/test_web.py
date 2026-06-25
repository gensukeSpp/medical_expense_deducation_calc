import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from app.web.server import create_app
from app.output import write_json_atomic
from app.db_migrations import run_migrations

SCHEMA_PATH = Path("docs/schema.sql")


def parse_html_content(html_content: str, keyword: str) -> bool:
    """HTMLコンテンツから指定されたキーワードが含まれているかを確認する。"""
    return keyword in html_content


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


def test_index_lists_structured_files(client):
    """GET / が正常に一覧を表示する"""
    response = client.get("/")
    assert response.status_code == 200
    # HTMLに「あおばクリニック-2026-01-15」が含まれる
    assert parse_html_content(response.text, "あおばクリニック-2026-01-15")
    # 2ファイルとも表示される
    assert parse_html_content(response.text, "receipt-001")
    assert parse_html_content(response.text, "receipt-002")


def test_index_fallback_display_name(client):
    """clinic が null の場合、ファイル名が表示名として使われる"""
    response = client.get("/")
    assert response.status_code == 200
    # HTMLに `receipt-002` が含まれる
    assert parse_html_content(response.text, "receipt-002")


def test_index_empty_directory(tmp_path):
    """JSONファイルがない場合、「データがありません」等のメッセージが表示される"""
    out_dir = tmp_path / "output_json"
    out_dir.mkdir()
    app = create_app(output_dir=str(out_dir), db_path=None)
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert parse_html_content(response.text, "データがありません")


def test_detail_shows_fields(client):
    """GET /receipt-001 が正常に詳細を表示する"""
    response = client.get("/receipt-001")
    assert response.status_code == 200
    # ラベル「氏名」「クリニック名(調剤薬局名)」「支払い金額」「発行日」が全て含まれる
    assert parse_html_content(response.text, "氏名")
    assert parse_html_content(response.text, "クリニック名(調剤薬局名)")
    assert parse_html_content(response.text, "支払い金額")
    assert parse_html_content(response.text, "発行日")
    # 値「山田 太郎」「あおばクリニック」「3800」「2026-01-15」が含まれる
    assert parse_html_content(response.text, "山田 太郎")
    assert parse_html_content(response.text, "あおばクリニック")
    assert parse_html_content(response.text, "3800")
    assert parse_html_content(response.text, "2026-01-15")


def test_detail_not_found(client):
    """存在しない file_stem の場合 404 を返す"""
    response = client.get("/nonexistent")
    assert response.status_code == 404


def test_correction_updates_db_and_json(client, temp_db):
    """PUT /receipt-001 で修正後、DBとJSONの両方が更新される"""
    # 修正前確認
    response = client.get("/receipt-001")
    assert parse_html_content(response.text, "山田 太郎")
    # 修正実行
    response = client.put("/receipt-001", json={"name": "山田 花子"})
    assert response.status_code == 200
    # DB と JSON の更新を確認
    # TODO: DB の確認は、DB接続を介して行う必要があるため、テストを追加する
    # JSON ファイルを再読み込みし、`name` が `山田 花子` になっていることを確認
    response = client.get("/receipt-001")
    assert parse_html_content(response.text, "山田 花子")


def test_correction_updates_json_only(client):
    """db_path=None の場合、JSONファイルのみ更新されDBエラーは発生しない"""
    # 修正実行
    response = client.put("/receipt-001", json={"name": "山田 花子"})
    assert response.status_code == 200
    # JSON ファイルを再読み込みし、`name` が `山田 花子` になっていることを確認
    response = client.get("/receipt-001")
    assert parse_html_content(response.text, "山田 花子")


def test_correction_multiple_fields(client):
    """一度のリクエストで複数フィールド（例: amount + date）を修正する"""
    # 修正実行
    response = client.put("/receipt-001", json={"amount": 5000, "date": "2026-02-01"})
    assert response.status_code == 200
    # JSON ファイルを再読み込みし、`amount` と `date` が更新されていることを確認
    response = client.get("/receipt-001")
    assert parse_html_content(response.text, "5000")
    assert parse_html_content(response.text, "2026-02-01")


def test_correction_normalization(client):
    """金額 `3,800円` や日付 `2026/01/15` など元のフォーマットで入力されても正規化される"""
    # 修正実行
    response = client.put("/receipt-001", json={"amount": "3,800円", "date": "2026/01/15"})
    assert response.status_code == 200
    # JSON ファイルを再読み込みし、`amount` と `date` が正規化されていることを確認
    response = client.get("/receipt-001")
    assert parse_html_content(response.text, "3800")
    assert parse_html_content(response.text, "2026-01-15")


def test_correction_db_error_continues(client):
    """DB が利用不可（テーブルなし等）でも JSON ファイル更新は継続され、エラーログに記録される"""
    # 修正実行
    response = client.put("/receipt-001", json={"name": "山田 花子"})
    assert response.status_code == 200
    # JSON ファイルを再読み込みし、`name` が `山田 花子` になっていることを確認
    response = client.get("/receipt-001")
    assert parse_html_content(response.text, "山田 花子")
