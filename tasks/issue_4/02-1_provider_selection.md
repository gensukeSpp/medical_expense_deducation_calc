# 02-1: LLM プロバイダ選定メモ

候補:
- HuggingFace (mistralai/Mistral-7B-Instruct-v0.3): オープン、ローカルまたは HF API 経由で利用可能
- OpenAI: 高い品質だが API コストと依存性がある
- Anthropic/Other: 商用 API オプション

選定基準:
- 日本語理解の強さ
- レイテンシ/コスト
- オフライン実行の可否（ローカルでの検証が重要）

現時点: テストは MockLLMClient を用い、実運用時に Mistral を検討する。