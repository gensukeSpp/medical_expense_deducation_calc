# 01-4: エラー処理ポリシー

方針:
- 個別ファイルの解析で例外が発生しても、バッチ全体の処理は継続する。
- 例外は output_json/errors.log に JSON Lines 形式で追記する（file, error, traceback, context を含む）。
- 致命的な初期化エラー（設定ファイルが破損など）は処理を停止する。
- 解析結果に null が入るのは許容。UI 側でユーザーが修正できる前提。

ログ項目例:
{"file": "output.json", "error": "ValueError:...", "step": "llm_extract", "timestamp": "2026-06-16T..."}
