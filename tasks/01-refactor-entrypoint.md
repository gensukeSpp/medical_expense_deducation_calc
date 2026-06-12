# 01 - Entrypoint リファクタリング

目的
- main.py を薄い CLI（設定読み込み・起点）にし、OCR 実行ロジックを app/ocr_pipeline.py 等へ移す。

受け入れ条件
- main.py は設定（入力フォルダ、出力フォルダ）を受け取り、処理は app/ 以下のモジュールに委譲される
- 新しいモジュールに対するユニットテストが少なくとも 1 つ存在する

小タスク
- app/ocr_pipeline.py を作成（既存ロジックの移植）
- CLI 引数（--input-dir, --output-dir, --mode）を追加
- main.py を簡潔に保つ
