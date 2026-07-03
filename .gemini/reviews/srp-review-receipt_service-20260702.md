# SRP Review: `app/services/receipt_service.py`

レビュー日: 2026-07-02
対象ファイル: `app/services/receipt_service.py`

## 1. 責務の特定 (Identification of Responsibilities)

`ReceiptService` クラスは、現時点で以下の多岐にわたる責務を負っています。

1.  **ファイルシステム操作**: JSON ファイルの検索、読み込み、書き込みの管理。
2.  **データ整形/プレゼンテーション**: JSON データから一覧表示用、詳細表示用のデータを生成・整形。
3.  **ビジネスロジック (OCR データの更新)**: データの正規化、更新。
4.  **データベース操作**: レシート情報、補正記録、クリニック情報のCRUD、およびトランザクション管理。
5.  **OCR 座標最適化/フィードバックループ**: OCR 処理結果に対する座標検索、テンプレートマッチング、学習データの更新（`process_correction_feedback` の呼び出し）。
6.  **エラーハンドリング**: 処理全般におけるエラーのキャッチと `app/error_logging` への記録。

## 2. SRP 違反の特定 (SRP Violations)

`ReceiptService` は「Receipt に関するサービス」という包括的な名前の下に、上記のような低レイヤー（ファイルIO、DB IO）から高レイヤー（正規化ルール、学習フィードバックロジック）までをすべて詰め込んでおり、強力な SRP 違反状態にあります。

特に `update_receipt` メソッドは、以下の理由で修正・テストが極めて困難です。

*   **密結合**: データベーススキーマやファイルフォーマットの構造を直接操作しており、それらが変更されると本クラスを修正する必要があります。
*   **高凝集度なロジック**: 座標フィードバックのための複雑な OCR エントリの探索ロジック、DB トランザクション処理、正規化が混在しており、メソッドが肥大化しています。
*   **テストの困難さ**: DB、ファイルシステム、他のサービス（`app/coord_search`, `app/template_feedback`）との副作用を切り離して単体テストを行うことができません。

## 3. 改善案の提示 (Proposed Improvements)

以下の責務分離を提案します。

| 現状の責務 | 推奨される分離先 |
| :--- | :--- |
| ファイル IO | `ReceiptFileRepository` |
| DB IO | `ReceiptDatabaseRepository` |
| データ整形/DTO | `ReceiptPresenter` (または JSON マッパー) |
| 正規化ロジック | `ReceiptNormalizer` |
| 座標検索ロジック | `OCRCoordinateService` |
| トランザクション/調整 | `ReceiptUpdater` (オーケストレーター) |

### 具体的なコード例（リファクタリング案）

`ReceiptService` をオーケストレーターとして機能させ、詳細な処理は各リポジトリやサービスに委譲します。

```python
class ReceiptService:
    def __init__(self, file_repo, db_repo, normalizer, coord_service):
        self.file_repo = file_repo
        self.db_repo = db_repo
        self.normalizer = normalizer
        self.coord_service = coord_service

    def update_receipt(self, file_stem: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        # 1. データの読み込み
        old_data = self.file_repo.load(file_stem)
        
        # 2. 正規化
        updated_data = self.normalizer.normalize(updates, old_data)
        
        # 3. DB 更新
        receipt_id = self.db_repo.update_receipt_data(file_stem, updated_data)
        
        # 4. 座標最適化 (フィードバックループ)
        feedback = self.coord_service.update_coordinates(
            receipt_id, updated_data, file_stem
        )
        
        # 5. ファイル更新
        self.file_repo.save(file_stem, updated_data)
        
        return {"status": "updated", "data": updated_data, "feedback": feedback}
```

このように責務を分離することで、`ReceiptService` は処理の流れを制御することに集中でき、各依存コンポーネントを独立してテスト・修正可能になります。
