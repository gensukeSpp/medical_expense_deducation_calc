from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import glob
from app.input import read_json
from app.output import write_json_atomic
from app.normalization import normalize_extracted
from app.db import insert_receipt, get_receipt, add_correction
from app.error_logging import append_error

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def create_app(output_dir: str = "output_json", db_path: str | None = None) -> FastAPI:
    """FastAPI アプリケーションを生成するファクトリ関数。テストで使用可能。"""
    app = FastAPI()

    def get_output_dir() -> Path:
        return Path(output_dir)

    def get_db_path() -> Path | None:
        return Path(db_path) if db_path else None

    @app.get("/", response_class=HTMLResponse)
    async def read_root(
        request: Request, output_dir: Path = Depends(get_output_dir), db_path: Path | None = Depends(get_db_path)
    ):
        """一覧ページを表示"""
        files = glob.glob(str(output_dir / "*-structured_data.json"))
        items = []
        for file_path in files:
            try:
                data = read_json(Path(file_path))
                file_stem = Path(file_path).stem.replace("-structured_data", "")
                clinic = data.get("clinic")
                date = data.get("date")
                if clinic and date:
                    display_name = f"{clinic}-{date}"
                else:
                    display_name = file_stem
                items.append({"file_stem": file_stem, "display_name": display_name, "clinic": clinic, "date": date})
            except Exception as e:
                # エラー時はスキップし、エラーログに記録
                append_error(output_dir, file_path, str(e), "read_index", {})
                continue

        # TemplateResponse のシグネチャは TemplateResponse(request, name, context, ...)
        return templates.TemplateResponse(request=request, name="index.html", context={"items": items})

    @app.get("/{file_stem}", response_class=HTMLResponse)
    async def read_item(
        request: Request,
        file_stem: str,
        output_dir: Path = Depends(get_output_dir),
        db_path: Path | None = Depends(get_db_path),
    ):
        """詳細ページを表示"""
        file_path = output_dir / f"{file_stem}-structured_data.json"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        data = read_json(file_path)
        # ラベルマッピング
        fields = [
            ("name", {"label": "氏名", "value": data.get("name", "")}),
            ("clinic", {"label": "クリニック名(調剤薬局名)", "value": data.get("clinic", "")}),
            ("amount", {"label": "支払い金額", "value": data.get("amount", "")}),
            ("date", {"label": "発行日", "value": data.get("date", "")}),
        ]
        # Jinja2のキャッシュエラーを避けるために、タプル内の辞書を文字列に変換
        # fields = [(k, str(v)) for k, v in fields]

        return templates.TemplateResponse(
            request=request, name="detail.html", context={"file_stem": file_stem, "fields": fields}
        )

    @app.put("/{file_stem}")
    async def update_item(
        file_stem: str,
        request: Request,
        output_dir: Path = Depends(get_output_dir),
        db_path: Path | None = Depends(get_db_path),
    ):
        """修正処理"""
        # リクエストボディから修正値を取得（JSONとFormデータの両方に対応）
        content_type = request.headers.get("content-type", "")
        updates = {}
        if "application/json" in content_type:
            try:
                json_data = await request.json()
                for key, value in json_data.items():
                    if key in ["name", "clinic", "amount", "date"]:
                        updates[key] = value
            except Exception:
                pass
        else:
            form_data = await request.form()
            for key, value in form_data.items():
                if key in ["name", "clinic", "amount", "date"]:
                    updates[key] = value

        # JSONファイルから現在値を読み取り
        file_path = output_dir / f"{file_stem}-structured_data.json"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        old_data = read_json(file_path)

        # 先にJSONファイル更新用のデータを作成し、金額・日付を正規化
        updated_data = {**old_data, **updates}
        updated_data = normalize_extracted(updated_data, old_data)

        # DB処理
        if db_path:
            try:
                receipt = get_receipt(db_path, file_stem)
                if receipt:
                    receipt_id = receipt["id"]
                else:
                    # レコードが存在しない場合は新規登録
                    receipt_id = file_stem
                    insert_receipt(db_path, receipt_id, str(file_path), None, old_data)
                # 修正を記録
                for field_name, new_value in updates.items():
                    old_value = old_data.get(field_name)
                    add_correction(db_path, f"{file_stem}-{field_name}", receipt_id, field_name, old_value, new_value)
            except Exception as e:
                # エラー時は処理を継続し、エラーログに記録
                append_error(output_dir, str(file_path), str(e), "update_item_db", {})
                pass

        # JSONファイル更新
        write_json_atomic(file_path, updated_data)

        # 更新後の値を含むHTML断片を返却
        # ここでは簡略化のため、更新後の値を含むHTMLを返す
        # 実際には、更新後の値を含むHTML断片を返す必要がある
        # 今回は、更新後の値を含むHTMLを返す代わりに、更新後の値をJSONとして返す
        return {"status": "updated", "data": updated_data}

    return app


# デフォルトのアプリケーションインスタンス
app = create_app()
