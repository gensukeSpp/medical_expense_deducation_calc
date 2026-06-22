# RealLLMClient 実装計画 (plan mode)

目的
- mistralai/Mistral-7B-Instruct-v0.3 を用いる RealLLMClient を実装し、現行の MockLLMClient の代替として構成可能にする。
- パイプライン (OCR -> LLM 抽出 -> 正規化 -> 出力) を本番L L Mで動かせるようにする一方、モックへのフォールバックを保持する。

要件 / 受入条件
- CLI/設定で --model に `mistralai/Mistral-7B-Instruct-v0.3` を指定すると、実際に LLM 推論を呼び出す。
- 認証情報は環境変数 `HF_API_TOKEN`（または同等）で設定できる。
- タイムアウト、リトライ、例外処理を備え、例外時には pipeline が落ちずログに記録される。
- レスポンスは既存の LLM 抽出インタフェース（extract_fields -> dict{name,clinic,amount,date}）に準拠する。
- 統合テストはトークンがない環境ではスキップされる（CI を壊さない）。

設計案（推奨）
- 手法: Hugging Face Inference API（HTTP）経由でモデルを呼び出す。
  - 理由: 環境依存が少なく、ローカル GPU/依存性の追加を避けられるため導入コストが低い。
  - 実装ライブラリ候補: `huggingface-hub` または `httpx` + `huggingface-hub` の minimal wrapper。
- 代替: transformers を用いたローカル実行（GPU 必須・環境負荷大） — 将来的に検討。

RealLLMClient API（要件）
- class RealLLMClient:
  - __init__(model_name: str, api_token: Optional[str]=None, timeout: int=30, retries: int=2)
  - extract_fields(self, ocr_lines: list[dict]) -> dict
    - 入力: OCR 出力（既存の形）
    - 出力: {"name": str|None, "clinic": str|None, "amount": int|None, "date": str|None}
    - 失敗時: raise 例外または戻り値内で None を返すが、呼び出し側（structural_parser）で捕捉されログ出力/フォールバックが行われる。

Prompt と入出力フォーマット
- 既存の prompt テンプレートを `app/prompts.py` に集中（存在しない場合は新規作成）。
- LLM にはJSON または明確な鍵付きレスポンスを要求するプロンプトを与え、パースを堅牢化する。
- 例: "Return JSON with keys name, clinic, amount, date. If unknown, use null." と明示する。

エラーハンドリング
- HTTP タイムアウト、非200、デコード失敗は捕捉し、構造化ログ（app/error_logging.py へ append_error）に追記。
- リトライは指数バックオフ（最大 retries 回）を実装。
- 異常時は MockLLMClient にフォールバックできる設計にする（factory レイヤで実現）。

テスト
- unit:
  - RealLLMClient のレスポンスパース関数を isolated にテスト（LLM 応答文字列 -> dict）
  - 異常ケース（タイムアウト、不正JSON）で structural_parser がエラーを記録するテスト
- integration (optional, スキップ条件付き):
  - HF_API_TOKEN 環境変数がある場合のみ実行。小さな入力を実際に呼び出して正常系フローを確認する。
- CI: integration は `-m integration` 等で分離し、トークンがない環境でスキップされることを確認する。

pyproject.toml / 依存関係
- 追加候補:
  - huggingface-hub >= 0.x または httpx >= 0.x
  - (optional) tenacity などリトライ用
- README に HF_API_TOKEN とコスト/注意点を追記。

ファイル変更一覧（影響がありそうなファイル）
- 追加/更新
  - app/llm_client.py  <-- 新規: RealLLMClient + helper (API呼出し, パース, retry)
  - app/prompts.py      <-- 新規または拡張: プロンプトテンプレートと例
- 変更
  - app/llm_extractor.py <-- get_llm_client() を使用するよう整理、Mock のまま残す
  - app/args.py         <-- --model オプションのデフォルト/説明を確認、--hf-token フラグを検討
  - app/structural_parser.py <-- RealLLMClient からの例外に対応するテスト追加、ログ/エラー記録の確認
  - app/error_logging.py <-- (既存あれば) エラーフォーマットに model, request_id を追加
  - main.py             <-- 動作確認スイッチ（--model 指定例）を README と合わせる
  - tests/test_llm_real_client.py <-- unit + integration テスト（integration は skip 条件付き）
  - tasks/issue_4/expected/* <-- integration 用の記録済みレスポンス（fixtures）
  - pyproject.toml      <-- 依存追記
  - README.md           <-- 使用方法と環境変数の記載

移行手順（実装フェーズ）
1. prompts.py を作成し、期待するレスポンス例を定義する。
2. app/llm_client.py (RealLLMClient) の雛形を実装（API 呼び出し + JSON パース）。
3. get_llm_client ファクトリを更新して model 名から Mock/Real を返せるようにする。
4. CLI と README を更新（HF_API_TOKEN の説明、デフォルトの注意）。
5. unit テストを追加。CI の設定は integration テストを skip するように変更。
6. 手元で HF_API_TOKEN をセットして integration を実行、期待通りに動くことを確認。
7. PR を作成し、レビュー/マージ後にデプロイ手順を更新。

PR チェックリスト
- [ ] RealLLMClient の実装コードが追加されている
- [ ] ユニットテストが追加され、パスしている
- [ ] Integration テストは HF_API_TOKEN がない状態でスキップされる
- [ ] README / pyproject.toml の更新が含まれている
- [ ] ログ/エラー出力が既存 spec に準拠している
- [ ] get_llm_client の移行が完了し、既存 Mock が壊れていない

概算作業時間
- 設計 + 実装（初期プロトタイプ）: 4–8 時間
- テスト追加 + CI 調整: 1–2 時間
- ドキュメント・レビュー: 1 時間

リスクと緩和策
- API トークン/コストリスク: README に注意喚起。Integration は developer opt-in にする。
- レスポンス不安定: 明確なプロンプトと厳格な JSON パースを採用し、非整形レスポンスはエラーとして扱う。
- 環境差: HF を使うことでローカル GPU に依存しないが、レイテンシと課金に注意。

次のアクション（推奨）
- この plan をレビューして承認を確認後、RealLLMClient を実装するブランチを切る。
- 実装ブランチ名例: `issue-4/real-llm-client`

---
Plan created: REAL_LLM_CLIENT_PLAN.md
