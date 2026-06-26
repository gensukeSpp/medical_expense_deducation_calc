# Project: Medical Expense Deduction Calculator

自動OCR + LLM により医療費領収書からデータを抽出し、税控除申告を支援するアプリケーション。
「Human-in-the-Loop」設計で、ユーザー修正を学習しクリニック固有のレイアウト精度を向上させる。

## Architecture & Technologies

```
Language: Python (>=3.11)
OCR:      PaddleOCR (text + coordinate extraction)
Image:    OpenCV (resize, grayscale via cv2.INTER_CUBIC)
LLM:      Structural LLM + Naming Extractor LLM (structured JSON 化)
DB:       SQLite (data/db.sqlite3)
Web:      FastAPI + uvicorn + Jinja2 + htmx
Lint:     Black (line-length 119)
```

### Dataflow

```
input image → image_resize (short side = 960px, grayscale)
            → PaddleOCR (lang="japan")
            → structural_parser (LLM or mock heuristic)
            → normalization (date, amount, clinic name)
            → output JSON + SQLite persistence
            → Web UI (confirm/correct via FastAPI + htmx)
```

## Key Files & Directories

| Path | Purpose |
|---|---|
| `main.py` | Entrypoint: CLI dispatch, watcher, single-image, Web server |
| `app/args.py` | Argument parsing, CUDA env setup (`CUDA_VISIBLE_DEVICES=-1` default) |
| `app/ocr_pipeline.py` | PaddleOCR text + coordinate extraction |
| `app/image_resize.py` | Image preprocessing (resize, grayscale) |
| `app/structural_parser.py` | LLM / mock structural output parsing |
| `app/normalization.py` | Text, amount, date, clinic name normalization |
| `app/llm_extractor.py` | LLM API interface for extraction |
| `app/watcher.py` | Directory watcher (watchdog observer / polling loop) |
| `app/processor.py` | Single-image processing pipeline orchestrator |
| `app/db.py` | SQLite CRUD: receipts, corrections, clinic templates |
| `app/error_logging.py` | Centralized error logging |
| `app/coord_search.py` | Coordinate correction / search logic |
| `app/template_feedback.py` | User feedback → template learning |
| `app/prompts.py` | LLM prompt templates |
| `app/services/receipt_service.py` | Service layer: business logic orchestration |
| `app/web/server.py` | FastAPI Web UI (review/correct extracted data) |
| `app/web/templates/` | Jinja2 templates for Web UI |
| `tests/` | Unit + integration + E2E test suites (10 test files) |
| `tasks/issue_N/` | Issue-specific task plans and E2E runners |
| `docs/` | Architecture docs, schema definitions (`schema.sql`) |
| `pyproject.toml` | Project config, dependencies, Black config |
| `要件定義書.md` | Core requirements and functional spec (Japanese) |

## Environment / Run / Test / Lint

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
uv add --editable .
```

Dependencies are managed in `pyproject.toml` (no lockfile). Key deps:
- `paddleocr[doc-parser]>=3.6.0`, `paddlepaddle>=3.3.1`
- `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`, `httpx2`
- `watchdog>=6.0.0`, `pytest>=9.0.3`, `black>=26.5.1`

### Run

```bash
# Directory watcher (watchdog mode — inotify)
uv run main.py --watch --use-watchdog

# Directory watcher (polling mode, every 10 s)
uv run main.py --watch

# Process a single OCR JSON → structured output
uv run main.py --input-json <path> --output-dir <dir>

# Process a single image by name from ~/Downloads/receipts/
uv run main.py --image-name IMG_20260101_xxx.jpg

# Start Web UI (review/correct extracted data)
uv run main.py --serve --db-path data/db.sqlite3

# Combine: watch + Web UI + DB persistence
uv run main.py --watch --use-watchdog --serve --db-path data/db.sqlite3
```

> **CPU-first default:** `app/args.py` sets `CUDA_VISIBLE_DEVICES="-1"` unless overridden.
> To use GPU: `CUDA_VISIBLE_DEVICES=0 uv run main.py ...`

### Test

```bash
# All tests
pytest -q

# Single test
pytest tests/test_file.py::test_name
pytest -k <expr>

# E2E test
uv run tasks/issue_4/run_e2e.py
```

### Lint

```bash
black .                          # format all
black path/to/file.py            # format single file
```

Convention: run Black before committing. Config in `pyproject.toml` (line-length 119).

## Development Conventions

- **Type Safety**: Use type hints (`from __future__ import annotations` for forward refs).
- **Code Style**: PEP 8 + Black (line-length 119).
- **Docstrings**: Google-style with `Args:` / `Returns:`.
- **Imports**: Standard lib → third-party → local; absolute imports preferred.
- **Modularity**: Clean separation between OCR, LLM, normalization, persistence, and Web layers.
- **Service Layer**: Cross-module business logic lives in `app/services/`.
- **Testing**: pytest. Prefer integration tests with real DB/fixtures over mocks.
- **Security**: No hardcoded secrets. Use env vars for configuration.

## Current Progress

### Implemented
- OCR → LLM extraction → normalization pipeline (fully integrated)
- CLI: `--watch`, `--use-watchdog`, `--input-json`, `--image-name`, `--model`, `--serve`
- Normalization: dates, clinic names, monetary values (robust)
- Web UI: FastAPI + htmx for review/correction
- DB persistence: SQLite with receipts, corrections, clinic templates
- Service layer: `app/services/receipt_service.py`
- Coordinate correction + user feedback loop
- E2E testing framework

### In Progress / Upcoming
- Template correction value learning (real-world data)
- Coordinate-to-field mapping refinement
- Expanded test coverage for service layer