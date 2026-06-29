# SRP Review: `app/structural_parser.py`

## 1. 責務の特定 (Responsibilities)
`app/structural_parser.py` の `process_input_json` 関数は、以下の責務を担っています。

1.  **入力処理**: OCR結果（JSONファイル）の読み込み。
2.  **情報抽出**: LLMを利用したデータの抽出。
3.  **テンプレートベースの補正**: 近接検索によるフィールド抽出の補正（ヒューリスティック/テンプレートマッチング）。
4.  **正規化**: 抽出されたデータの正規化。
5.  **出力処理**: 構造化されたデータのファイルへの書き出し。
6.  **永続化**: データベース（SQLite）へのレシートデータおよびクリニック情報の登録。
7.  **エラーハンドリング**: 各工程におけるエラーの補足とログ記録。

## 2. SRP 違反の特定 (SRP Violations)

`process_input_json` は「オーケストレーター」として機能すべきですが、実質的にはすべてのロジックを直接実行しており、以下の理由でSRPに違反しています。

*   **密結合**: この関数はファイルシステム（入出力）、外部サービス（LLM）、データベース（SQLite）、正規化ロジック、テンプレートマッチングロジックすべてに直接依存しています。
*   **変更の影響範囲**: LLM抽出方法の変更、データベーススキーマの変更、ファイル出力フォーマットの変更などがすべてこの関数の変更を必要とします。
*   **テスタビリティの低さ**: これらすべての依存関係が混在しているため、単体テストが極めて困難です。

## 3. 改善案の提示 (Proposed Improvements)

「オーケストレーター」として、責務を各専門クラス/サービスに委譲する設計を推奨します。

### 推奨構造
*   `ReceiptProcessingService`: 全体ワークフローの指揮（今の `process_input_json` の役割を縮小）。
*   `OCRResultLoader`: 入力JSONの読み込み担当。
*   `ExtractionService`: LLMおよびテンプレートベースの抽出担当。
*   `DataNormalizationService`: 正規化担当。
*   `ReceiptRepository`: DBへの永続化担当。
*   `OutputWriter`: 構造化データの保存担当。

### リファクタリング後のイメージ

```python
class ReceiptProcessingService:
    def __init__(self, extractor, normalizer, repository, writer):
        self.extractor = extractor
        self.normalizer = normalizer
        self.repository = repository
        self.writer = writer

    def process(self, input_path):
        ocr_data = OCRResultLoader.load(input_path)
        raw_data = self.extractor.extract(ocr_data)
        normalized = self.normalizer.normalize(raw_data)
        
        self.writer.write(normalized)
        self.repository.save_receipt(normalized)
        return normalized
```

この分離により、各クラスは単一の責務に集中し、テストや保守が容易になります。
