# SRP Review: app/services/ocr_coordinate_service.py

## 1. 責務の特定
このクラスは現在、以下の理由で変更される可能性があります：

1.  **OCRデータの取得源の変更**: DBからの取得方法、ファイルからの取得方法、または検索パターンが変わった場合。
2.  **座標検索アルゴリズムの変更**: テキストマッチング、近接検索、あるいは将来追加される新しい検索手法のロジック自体が変わった場合。
3.  **フィードバック処理のフロー変更**: 修正プロセス全体の手順（検索→調整→DB反映）が変わった場合。
4.  **エラーログの形式変更**: エラーの記録方法が変わった場合。

## 2. SRP 違反の特定

クラス `OCRCoordinateService` は「OCRデータのリポジトリ管理」「座標検索アルゴリズムの実行」「フィードバックのオーケストレーション」という複数の責務を負っています。

- **データアクセスと検索ロジックの混在**: `_get_ocr_entries` や `_load_raw_data` はリポジトリの役割です。
- **アルゴリズムの直接実装**: `_find_multi_boxes_by_substring` のような複雑な検索ロジックがサービス内にハードコードされています。

## 3. 改善案の提示

### 3.1 リポジトリへの責務委譲
OCRデータの取得は、既存の `ReceiptFileRepository` や `ReceiptDatabaseRepository` に完全に委譲し、このクラスには持たせないようにします。

### 3.2 検索エンジンの分離
座標検索（テキスト、近接、部分文字列）は、`OCRCoordinateSearchStrategy` のような抽象化されたクラス群（Strategyパターン）に切り出します。

### 3.3 クラス構造の例

```python
# 提案される責務分担
class OCRCoordinateService:
    def __init__(self, repository, search_engine, feedback_processor):
        self.repository = repository
        self.search_engine = search_engine
        self.feedback_processor = feedback_processor

    def process_feedback(self, ...):
        ocr_entries = self.repository.get_entries(...)
        coords = self.search_engine.search(ocr_entries, updates)
        return self.feedback_processor.process(coords, ...)
```

この変更により、データアクセス、検索ロジック、反映処理をそれぞれ独立して変更できるようになります。
