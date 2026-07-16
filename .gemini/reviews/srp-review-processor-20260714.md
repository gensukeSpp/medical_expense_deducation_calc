# SRP Review: app/processor.py

**Date:** 2026-07-14
**Target File:** `app/processor.py`
**Reviewer:** Clean Code Specialist

---

## 1. 責務の特定

`process_single_image` 関数は、現在以下の責務を混在させて担っています：

1.  **入力バリデーション**: `args.image_name` の存在チェックおよび `input_dir` 内であることの保証。
2.  **ファイルシステム操作**: ファイルの最終更新時刻取得、出力パスの決定。
3.  **OCRパイプラインのオーケストレーション**: `app.ocr_pipeline.process_image` の呼び出し。
4.  **後続処理のオーケストレーション**: 座標正規化 (`app.coord_normalizer`) および構造解析 (`app.structural_parser`) の実行順序制御。
5.  **データ加工 (ポストプロセッシング)**: `low_confidence` フラグが立った場合の構造化データへの追加書き込み。
6.  **エラーハンドリングとロギング**: 全プロセスにわたる複雑な例外処理とログ出力。
7.  **CLI制御**: `sys.exit()` を使用したアプリケーションの強制終了を含む、CLI特有の制御フロー。

## 2. SRP 違反の特定

本関数は、古典的な「神関数 (God Function)」であり、**単一責任の原則 (SRP) を著しく違反**しています。

- **変更理由が多すぎる**: 入力バリデーションのルール変更、ファイル名の命名規則変更、OCRエンジンの変更、構造解析のアルゴリズム変更、データ構造の変更など、あらゆる要素の変更がこの1関数に影響を及ぼします。
- **テスタビリティの欠如**: CLI引数 (`argparse.Namespace`) に依存しており、純粋なロジックとしてのテストが困難です。
- **結合度が高い**: 各モジュール (`ocr_pipeline`, `coord_normalizer`, `structural_parser`) を直接呼び出し、かつ詳細な制御フローを内部に持っています。

## 3. 改善案の提示

この責務を分離するために、以下のクラス構造へのリファクタリングを推奨します。

### 推奨構造: `ImageProcessingService`

`processor.py` は純粋なオーケストレーターとして、以下のようなクラスにロジックを委譲すべきです。

```python
# 構造案
class ImageProcessingService:
    def __init__(self, ocr_engine, db_repository):
        self.ocr_engine = ocr_engine
        self.db = db_repository

    def process(self, image_path: Path, output_dir: Path, model: str) -> None:
        """単一画像の処理フローを管理する"""
        raw_data = self._run_ocr(image_path, output_dir)
        norm_result = self._normalize(raw_data.path)
        structured_data = self._parse(raw_data.path, model)
        
        if norm_result.get("low_confidence"):
            self._apply_low_confidence_flag(structured_data.path)

    def _run_ocr(self, ...): ...
    def _normalize(self, ...): ...
    def _parse(self, ...): ...
```

### 具体的な改善方針

1.  **CLIとロジックの分離**: `argparse` 引数を解析する関数と、ビジネスロジックを実行するクラスを明確に分離します。`sys.exit()` はCLIハンドラ側にのみ存在させます。
2.  **オーケストレーターパターンの採用**: `ImageProcessingService` クラスを作成し、各ステップ（OCR、正規化、解析）の実行は、依存注入されたそれぞれの専用サービスに委譲します。
3.  **データオーグメンテーションの責務分離**: `low_confidence` フラグを追加するロジックは、現在の構造解析 (`structural_parser`) または別の `ReceiptAugmentor` サービスに切り出すべきです。

このリファクタリングにより、各コンポーネントが独立し、テストが容易になり、メンテナンス性が大幅に向上します。
