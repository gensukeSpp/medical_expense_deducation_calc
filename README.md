# medical-exp-deducation-calc

軽量な領収書 OCR パイプライン (PaddleOCR ベース)

## 使い方

1. 仮想環境を作成し有効化

   python -m venv .venv
   source .venv/bin/activate

2. 依存を追加（このプロジェクトでは uv を使います）

   uv add pytest
   uv add watchdog

3. 単一ファイル実行例

   python main.py --image-name IMG_20260611_143221.jpg

4. watcher を使う

   # ポーリングモード
   python app/watcher.py --input-dir ~/Downloads/receipts --output-dir output_json --run-once

   # inotify/watchdog モード
   python app/watcher.py --use-watchdog --input-dir ~/Downloads/receipts --output-dir output_json

5. 出力

   output_json/ に YYYYMMDD_{image_stem}-raw_data.json が作成されます。

## 開発

- Python 3.11 を推奨。pyenv を使って切り替えるか、システム Python を利用してください。
- テスト実行: pytest
- コード整形: black . (pyproject.toml の設定に従う)

## 追加情報
- 要件定義は 要件定義書.md を参照
