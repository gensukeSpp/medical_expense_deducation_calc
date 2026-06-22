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
- テスト実行: pytest (実行時は `PYTHONPATH=. pytest` や `python -m pytest` を使用してください)
- コード整形: black . (pyproject.toml の設定に従う)

## データベース (SQLite)

このアプリケーションは、抽出したデータや OCR 座標、ユーザーの修正データを永続化するために SQLite を使用します。

### 1. 初期化

以下のコマンドを実行して、データベースファイルを初期化しテーブルスキーマを作成します。
```bash
python -m app.db_migrations init --db-path data/db.sqlite3
```

### 2. データ永続化の有効化

CLI モードで結果をデータベースに保存するには、`--db-path` オプションを指定して実行します。
```bash
python main.py --input-json <path_to_ocr_json> --db-path data/db.sqlite3
```
※ `--db-path` を指定しない場合、DBへの書き込みは行われず、既存の JSON ファイル出力のみが行われます。

### 3. バックアップとデータ移行の注意点

- **バックアップ**: データベースは単一のファイル (`data/db.sqlite3`) に保存されます。バックアップを行う場合は、このファイルを別の安全な場所にコピーしてください。
- **データ移行 (マイグレーション)**: スキーマに変更がある場合は、`docs/schema.sql` を更新し、移行スクリプトを拡張するか手動で `ALTER TABLE` などを実行してください。本番環境のデータが上書きされないよう注意してください。
- **同時アクセス**: SQLite はファイルロックを使用するため、複数のプロセスから同時に書き込みを行うと `database is locked` エラーが発生することがあります。本番運用では書き込み要求が重ならないようにするか、タイムアウト設定を適切に行ってください。

## 追加情報
- 要件定義は 要件定義書.md を参照

