from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from app.services.receipt_service import ReceiptService

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def create_app(output_dir: str = "output_json", db_path: str | None = None) -> FastAPI:
    """FastAPI アプリケーションを生成するファクトリ関数。テストで使用可能。"""
    app = FastAPI()

    def get_output_dir() -> Path:
        return Path(output_dir)

    def get_db_path() -> Path | None:
        return Path(db_path) if db_path else None

    async def get_receipt_service(
        output_dir: Path = Depends(get_output_dir),
        db_path: Path | None = Depends(get_db_path),
    ) -> ReceiptService:
        return ReceiptService(output_dir, db_path)

    @app.get("/", response_class=HTMLResponse)
    async def read_root(request: Request, service: ReceiptService = Depends(get_receipt_service)):
        """一覧ページを表示"""
        items = service.get_all_receipts()
        return templates.TemplateResponse(request=request, name="index.html", context={"items": items})

    @app.get("/{file_stem}", response_class=HTMLResponse)
    async def read_item(
        request: Request,
        file_stem: str,
        service: ReceiptService = Depends(get_receipt_service),
    ):
        """詳細ページを表示"""
        try:
            detail = service.get_receipt_detail(file_stem)
            return templates.TemplateResponse(
                request=request, name="detail.html", context={"file_stem": file_stem, "fields": detail["fields"]}
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")

    @app.put("/{file_stem}")
    async def update_item(
        file_stem: str,
        request: Request,
        service: ReceiptService = Depends(get_receipt_service),
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

        try:
            result = service.update_receipt(file_stem, updates)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")

        # 座標未検出フィールドがある場合、エラー情報をレスポンスに含める
        coord_errors = result.get("coord_errors", [])

        # 更新後の値を含むHTML断片またはエラー情報を返却
        if coord_errors:
            return templates.TemplateResponse(
                request=request,
                name="coord_error.html",
                context={
                    "file_stem": file_stem,
                    "coord_errors": coord_errors,
                    "updated_data": result["data"],
                },
            )

        return {"status": "updated", "data": result["data"]}

    return app
