# Copilot instructions for medical-exp-deducation-calc

This repo implements an OCR-driven workflow for medical receipts used in tax deduction workflows. The core logic is not a generic Python app: it is a receipt-processing pipeline that combines PaddleOCR, structured extraction, normalization, SQLite persistence, and a human review loop.

## Build, test, and lint

Use Python 3.11+ and the project-managed `uv` environment.

```bash
python -m venv .venv
source .venv/bin/activate
uv pip install --upgrade uv[all]
uv add --editable .
```

Run the app:

```bash
# Watch a folder for new images
uv run main.py --watch --use-watchdog --input-dir ~/Downloads/receipts --output-dir output_json

# Polling mode for the same workflow
uv run main.py --watch --input-dir ~/Downloads/receipts --output-dir output_json

# Process one OCR JSON file into structured output
uv run main.py --input-json path/to/ocr_data.json --output-dir output_json

# Start the review UI
uv run main.py --serve --db-path data/db.sqlite3

# Initialize SQLite schema once
python -m app.db_migrations init --db-path data/db.sqlite3
```

Run tests:

```bash
pytest -q
pytest tests/test_normalization.py -v
pytest tests/test_normalization.py::test_parse_amount_numeric -v
pytest -k "test_parse" -v
uv run tasks/issue_4/run_e2e.py
```

Format and lint checks:

```bash
black .
black path/to/file.py
black --check .
```

Project defaults from `pyproject.toml`: Black is configured with `line-length = 119`.

## High-level architecture

The system is organized as a pipeline rather than a monolith:

- `main.py` is the entrypoint for CLI, directory watching, single-image processing, and the FastAPI review UI.
- `app/args.py` centralizes CLI config and defaults to `CUDA_VISIBLE_DEVICES=-1` so OCR runs CPU-first unless explicitly overridden.
- `app/image_resize.py` and `app/ocr_pipeline.py` handle image resizing/grayscale and PaddleOCR text/box extraction.
- `app/coord_normalizer.py` converts absolute OCR coordinates into relative coordinates to account for photography offsets and uses confidence gating (`low_confidence` when the top element is below 0.8).
- `app/llm_extractor.py` plus `app/structural_parser.py` convert OCR output into a structured receipt model and apply clinic/template corrections.
- `app/normalization.py` canonicalizes dates, amounts, and clinic names (including Japanese-era and kanji-based values).
- `app/services/` contains the orchestration layer for receipt processing, template matching, and DB-backed business logic.
- `app/db.py` and `docs/schema.sql` are the persistence boundary for receipts, clinic templates, coordinate corrections, and user feedback.
- `app/web/server.py` exposes the review UI where users verify/correct extraction results.

The practical flow is:

```text
receipt image
  -> resize/grayscale
  -> PaddleOCR text + coordinates
  -> coordinate normalization + low_confidence gating
  -> LLM/mock structuring + template matching
  -> normalization (date/amount/clinic)
  -> JSON output + SQLite persistence
  -> review UI for human corrections
  -> template learning for future receipts
```

Two processing paths matter in practice:

1. Image -> structured JSON: `main.py -> processor.py -> OCR pipeline -> extraction -> normalization -> save`
2. Existing OCR JSON -> structured data: `main.py -> structural_parser.process_input_json()`

Preserve that layering when changing code: OCR, normalization, persistence, and review UI each have distinct responsibilities.

## Key conventions

- Prefer the service/repository boundary already in `app/services/` and `app/db.py` instead of embedding DB logic in the web UI or parser layer.
- Keep CLI behavior centralized in `app/args.py`; when adding options, follow the existing `--watch`, `--input-json`, `--serve`, and `--db-path` patterns.
- `docs/schema.sql` is the source of truth for SQLite structure; if `--db-path` is used, initialize the schema with `python -m app.db_migrations init --db-path data/db.sqlite3`.
- Template matching is proximity-first and coordinate-aware. The repo uses hybrid matching: exact clinic name match, then text similarity, then layout-based matching (50px proximity / 60% field match).
- `low_confidence` receipts are special: they still record corrections, but template updates are skipped for those records to avoid poisoning the learning loop.
- Keep formatting consistent with existing imports and Black style: stdlib -> third-party -> local; line length is 119.
- Prefer targeted validation (`pytest tests/...` or `pytest -k <pattern>`) before broader runs; this repo is test-friendly but not heavy on full-suite execution.

## Project-specific notes

- `README.md`, `AGENTS.md`, `GEMINI.md`, and `QWEN.md` all describe the same core design: OCR-first receipt processing with SQLite-backed persistence and a human review loop.
- The app intentionally learns from user correction history to improve clinic-specific templates over time; changes around correction feedback, coordinate matching, and low-confidence handling should be treated as sensitive behavior.
