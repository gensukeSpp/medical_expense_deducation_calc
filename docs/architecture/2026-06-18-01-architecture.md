# 2026-06-18 — Architecture snapshot

PR: #7 — Issue #4: LLM-based extraction - initial implementation & tests

PR summary:
This PR adds a mock LLM extractor, OCR sample JSONs, input/output schemas, and unit tests to support Issue #4 (AI-based extraction of name, clinic, amount, and date).

Purpose
- Confirm OCR output schema and the expected LLM input/output schema for extracting structured fields (name, clinic, amount, date).
- Introduce a provider-agnostic LLM wrapper with timeout/retries and a mock interface for reliable unit testing.
- Record architectural decisions needed to later introduce a template cache and LLM-based clinic-name identification.

Overview
- Purpose: Convert normalized OCR JSON into structured records suitable for downstream storage and labeling by using an LLM-based extraction step.
- Core components:
  - app/llm_extractor.py: LLM call wrapper (timeout, retries, provider-agnostic interface, and mock support for tests).
  - app/prompts.py: Prompt template management and canonical prompts for extraction of (name, clinic, amount, date).
  - app/ocr_pipeline.py: Produces normalized OCR JSON that serves as LLM input; minor adaptations to include context for prompts.
  - app/processor.py: Orchestrates calling the OCR pipeline and the llm_extractor, and writing structured outputs.
  - app/watcher.py / main.py: trigger processing (single-file or watch mode) and integrate end-to-end flow.
- Dataflow: input image -> resize -> PaddleOCR -> normalize OCR JSON -> llm_extractor -> structured JSON -> output (atomic write)

Notes:
- Snapshot generated only for Python file changes as requested.
- PR body excerpt: "Files added: app/llm_extractor.py, app/prompts.py, tests/test_issue_4_llm_wrapper.py, tasks/issue_4/*"
- If further details (per-commit messages or diffs) are needed, run: `gh pr view 7 --json commits,files` or `gh pr diff 7` locally.

Generated-by: architecture-update skill (ad-hoc snapshot for PR #7)
