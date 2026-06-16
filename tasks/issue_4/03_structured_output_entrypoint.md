# issue-4-structured-output-entrypoint: CLI と入出力（分解）

目的:
- main.py に --input-json 引数を追加し、構造化出力ファイルを生成するエントリポイントを作る。

サブタスク:
- 03-1: CLI 引数追加（--input-json, --model, --output-dir）
- 03-2: 入力ファイルバリデーション（パス存在、JSON parse）
- 03-3: パーサ呼び出しの統合（structural_parser を呼ぶ）
- 03-4: output_json/{basename}-structured_data.json を書き出す処理
- 03-5: ログ出力（処理開始/終了、エラー）を追加
