# Issue #4: タスク一覧

- issue-4-design-prototype
  - タイトル: 実装方針とインターフェース仕様の策定
  - 説明: OCR JSON の想定スキーマ確認、LLMプロンプト設計、出力スキーマ定義、例外処理方針の文書化。

- issue-4-llm-integration
  - タイトル: LLM 呼び出しラッパー実装
  - 説明: Mistral 7B 用の呼び出しラッパーを作成（モデル名を設定可能）。呼び出し失敗時のリトライ/タイムアウト設定を含む。

- issue-4-structured-output-entrypoint
  - タイトル: 入力 JSON 指定と構造化出力のエントリポイント追加
  - 説明: main.py に `--input-json` 引数を追加し、output_json/{name}-structured_data.json を書き出す処理を呼び出す。

- issue-4-normalization-utils
  - タイトル: 金額・日付正規化ユーティリティの実装
  - 説明: 金額文字列から数値を取り出す関数、日付の多様な表記を ISO に正規化する関数を実装。

- issue-4-error-handling-continuation
  - タイトル: 例外発生時に処理を継続する仕組みの実装
  - 説明: 個別ファイルの解析で例外が出ても次ファイルに進む。エラーは output_json/errors.log に追記する。

- issue-4-mock-tests-missing-labels
  - タイトル: モックデータによるテストの実装（ラベル欠落ケース）
  - 説明: ラベルが欠落した場合の抽出精度を検証する pytest テストを作成。期待される出力を定義し検証する。

- issue-4-docs-update
  - タイトル: 要件定義書と README の更新
  - 説明: 要件定義書のステップ2に実装手順と CLI 使い方を追記。

- issue-4-integration-test-run
  - タイトル: 単体・統合テストを実行して結果を確認
  - 説明: pytest を使い、モックテストと簡易統合テストを実行。成功基準: 全テスト通過、出力ファイルが生成されること。
