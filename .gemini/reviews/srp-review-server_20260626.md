# SRP Review: `app/web/server.py`

## レビュー概要
`app/web/server.py` は現在、Webアプリケーションのエンドポイント定義だけでなく、ファイルシステム操作、データベース操作、データ正規化ロジック、および複雑なビジネスロジック（座標検索、フィードバック処理）を一つの関数に集約しており、単一責任の原則 (SRP) に強く違反しています。

## 1. 責務の特定
このファイル（特に `create_app` 内のハンドラ）は以下の責務を担っています。

1.  **Webインターフェースの提供**: FastAPIを用いたリクエスト/レスポンスのルーティングおよびHTMLレンダリング。
2.  **ファイルシステム操作**: JSONファイルの検索、読み込み、原子的な書き込み。
3.  **ビジネスロジックの実行**:
    *   データの正規化 (`normalize_extracted`)。
    *   OCRデータに基づく座標検索 (`coord_search`)。
    *   修正フィードバック処理 (`template_feedback`)。
4.  **データアクセス**: SQLiteデータベースへのレコード挿入、検索、修正記録。
5.  **エラーハンドリング**: 処理中のエラーを `error_logging` モジュールへ記録。

## 2. SRP 違反の特定
`update_item` 関数は、HTTPハンドラであるにもかかわらず、システムの「修正フロー全体」を制御しています。

*   **密結合**: コントローラー（ハンドラ）が、ファイルシステム、データベース、OCR処理モジュールに直接依存しています。
*   **責任の過多**: データベースの更新失敗時の処理や、座標検索アルゴリズムを呼び出すタイミングなど、本来ドメインサービスが持つべき知識をWebハンドラが知っています。

## 3. 改善案の提示

Webハンドラからロジックを分離し、サービスクラス（またはコントローラー）を導入することを提案します。

### 提案するアーキテクチャ
*   **Web層**: `app/web/server.py` (ハンドラのみ)
*   **サービス層**: `app/services/receipt_service.py` (ロジックの集約)
*   **データアクセス層**: `app/db.py`, `app/file_utils.py` (データの永続化と取得)

### コード例（改善後のイメージ）

```python
# app/services/receipt_service.py

class ReceiptService:
    def __init__(self, db_path, output_dir):
        self.db_path = db_path
        self.output_dir = output_dir

    def update_receipt(self, file_stem, updates):
        # 1. データ取得
        # 2. 正規化
        # 3. DB更新
        # 4. 座標検索・フィードバック
        # 5. ファイル更新
        # ロジックをここに集約
        pass
```

```python
# app/web/server.py

@app.put("/{file_stem}")
async def update_item(file_stem: str, request: Request, service: ReceiptService = Depends(get_service)):
    # ハンドラはリクエストのパースとサービス呼び出し、結果のレスポンス変換のみを行う
    updates = await parse_updates(request)
    result = service.update_receipt(file_stem, updates)
    return format_response(result)
```

この分離により、`server.py` はHTTPインターフェースの変更のみに影響を受け、ビジネスロジック（正規化や座標検索）は、コマンドラインツールや他のインターフェースから再利用可能になります。
