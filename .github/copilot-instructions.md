# Copilot instructions for medical-exp-deducation-calc

This repository processes medical receipts with OCR, LLM structuring, normalization, and a small FastAPI review UI. Most work centers on the receipt pipeline and the SQLite-backed template correction loop.

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

Project defaults from `pyproject.toml`: `black` is configured with `line-length = 119`.

## High-level architecture

The app is a pipeline for OCR + human review of medical receipts:

- `main.py` is the entrypoint: CLI args, watcher start, single-image processing, and FastAPI launch.
- `app/args.py` centralizes CLI configuration and sets `CUDA_VISIBLE_DEVICES=-1` by default to keep execution CPU-first unless explicitly overridden.
- `app/image_resize.py` resizes and grayscale-converts receipt images before OCR.
- `app/ocr_pipeline.py` runs PaddleOCR to extract text and bounding boxes.
- `app/llm_extractor.py` and `app/structural_parser.py` convert OCR text into a structured receipt model; the repo supports mock/local extraction as well as LLM-backed flows.
- `app/normalization.py` standardizes dates, amounts, and clinic names (including Japanese-era and kanji-based values).
- `app/services/` contains the orchestration layer for receipt processing, template matching, and database persistence.
- `app/db.py` and `docs/schema.sql` store receipts, clinic templates, coordinate corrections, and user feedback in SQLite.
- `app/web/server.py` provides a FastAPI UI for reviewing and correcting extracted data.

The practical flow is:

```text
receipt image
  -> resize/grayscale
  -> PaddleOCR text + coordinates
  -> LLM/mock structuring
  -> normalization + template matching
  -> JSON output + SQLite persistence
  -> review UI for human corrections
  -> template learning for future receipts
```

This repository intentionally keeps OCR, normalization, persistence, and UI logic separate; changes should respect that layering.

## Key conventions

- Prefer the service/repository boundary already in `app/services/` and `app/db.py` instead of embedding DB logic in UI or parser code.
- Keep CLI behavior centralized in `app/args.py`; when adding options, follow the existing `--watch`, `--input-json`, `--serve`, and `--db-path` patterns.
- Database writes are optional: if `--db-path` is provided, schema migration is expected (`python -m app.db_migrations init --db-path data/db.sqlite3`).
- Template matching is proximity-first and coordinate-aware; this repo has a documented multi-box handling pattern for split OCR fields and uses relative coordinate normalization to reduce photography offsets.
- `low_confidence` receipts are treated specially: the system should avoid template updates for low-confidence corrections while still recording corrections.
- Keep formatting consistent with Black and existing imports in order: stdlib -> third-party -> local.
- Prefer targeted validation with `pytest tests/...` or `pytest -k <pattern>` before broader runs.

## Notes from project docs

`README.md`, `QWEN.md`, and `GEMINI.md` all reflect the same architecture and usage patterns: this is an OCR-first medical receipt workflow with SQLite-backed persistence and a human review loop.
