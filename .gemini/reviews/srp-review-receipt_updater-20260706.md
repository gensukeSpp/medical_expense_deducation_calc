# SRP レビュー: `app/services/receipt_updater.py`

## 1. 責務の特定

`ReceiptUpdater` クラスは、現在以下の責務を担っています。

1.  **更新プロセスのオーケストレーション**:
    *   ファイルの読み込み、データ正規化、データベース更新、座標フィードバック処理、ファイルの保存という一連のフローを制御する。
2.  **データベース操作の詳細な制御**:
    *   データベースへのレコードの挿入、修正内容の保存、クリニックIDの管理、クリニックの検索・作成などの具体的な手順を知っている。
3.  **座標フィードバック処理のロジック**:
    *   OCRエントリのデータ構造の解析（`words` や `text_lines` の判定）。
    *   座標検索ロジックの選択と実行 (`search_coordinates`, `search_by_proximity_multi`)。
    *   テンプレートデータとOCRデータの突き合わせ判断。

## 2. SRP 違反の特定

`ReceiptUpdater` は「オーケストレーター」であるべきですが、実際には「ビジネスロジック」と「データアクセスの詳細（特に座標処理）」を混在させています。

*   **違反1: データベース操作の詳細知識**:
    *   `update_receipt` メソッド内で、レコードが存在しない場合の挿入ロジックや、修正内容（correction）の追加手順を直接実装しています。これにより、データベーススキーマの変更がこのクラスの修正を強制します。
*   **違反2: 座標処理ロジックの漏洩**:
    *   `_process_coordinate_feedback` メソッドが、OCRデータ構造を解析したり、具体的な座標検索アルゴリズムを呼び出したりしています。これにより、OCRデータのフォーマットや座標検索手法が変更された場合に、このクラスを修正する必要があります。

## 3. 改善案の提示

### 3.1 データベース操作の委譲
データベース操作に関するロジックを `ReceiptDatabaseRepository` に隠蔽します。`ReceiptUpdater` は「修正を保存する」という命令を出し、内部的なSQLや手順はリポジトリが管理すべきです。

### 3.2 座標処理の抽象化
`_process_coordinate_feedback` 内の複雑な解析ロジックを `OCRCoordinateService` に完全に移行します。

---

### 具体的な改善イメージ

#### 変更後: `ReceiptUpdater` (オーケストレーションに専念)

```python
class ReceiptUpdater:
    def update_receipt(self, file_stem: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        # 1. ロード
        old_data = self.file_repo.load_receipt(file_stem)
        
        # 2. 正規化
        updated_data = self.normalizer.normalize(updates, old_data)
        
        # 3. データベース更新 (詳細をリポジトリに隠蔽)
        feedback_info = self.db_repo.apply_receipt_updates(file_stem, old_data, updated_data, updates)
        
        # 4. 座標フィードバック (詳細を座標サービスに隠蔽)
        feedback_result = self.coord_service.process_feedback(file_stem, old_data, updated_data, updates, feedback_info)
        
        # 5. 保存
        self.file_repo.save_receipt(file_stem, updated_data)
        
        return { ... }
```

このようにすることで、`ReceiptUpdater` は「フローの制御」という唯一の責務に集中できるようになります。
