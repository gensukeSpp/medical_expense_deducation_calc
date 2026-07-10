# Copilot Instructions for medical-exp-deducation-calc

## Purpose

Guidance for Copilot sessions to efficiently work in this medical expense deduction calculator codebase—how to build, test, run, lint, and understand the system architecture.

## Build, Test, and Lint

**Python Version**: ≥ 3.11 (see `pyproject.toml`). Managed via `uv` package manager.

**Setup**:
```bash
python -m venv .venv
source .venv/bin/activate
uv pip install --upgrade uv[all]
uv add --editable .  # Install project dependencies from pyproject.toml
```

**Dependencies** (in `pyproject.toml`):
- PaddleOCR (text + coordinate extraction), PaddlePaddle (ML backend)
- FastAPI, uvicorn (Web UI server)
- pytest, watchdog (testing & file monitoring)
- Black (formatting, line-length 119)

**Running the Application**:
```bash
# Directory watcher (inotify mode, monitors for new receipts)
uv run main.py --watch --use-watchdog --input-dir ~/Downloads/receipts --output-dir output_json

# Directory watcher (polling mode, checks every 10s)
uv run main.py --watch --input-dir ~/Downloads/receipts --output-dir output_json

# Process a single OCR JSON file (CLI mode)
uv run main.py --input-json path/to/ocr_data.json --output-dir output_json

# Start Web UI server (FastAPI + Jinja2, port 8000)
uv run main.py --serve --db-path data/db.sqlite3

# Combine: watcher + Web UI + database persistence
uv run main.py --watch --use-watchdog --serve --db-path data/db.sqlite3

# Setup database schema (required once on first run)
python -m app.db_migrations init --db-path data/db.sqlite3
```

**Testing**:
```bash
# Run all tests
pytest -q

# Run a single test file
pytest tests/test_normalization.py -v

# Run a specific test
pytest tests/test_normalization.py::test_parse_amount_numeric -v

# Run tests matching a pattern
pytest -k "test_parse" -v

# Run E2E tests (mock LLM validation)
uv run tasks/issue_4/run_e2e.py
```

**Linting & Formatting**:
```bash
# Format entire project
black .

# Format specific file
black path/to/file.py

# Check without formatting
black --check .
```

**Configuration**: Black config in `pyproject.toml` (line-length = 119)

**Important Notes**:
- CPU-first default: `app/args.py` sets `CUDA_VISIBLE_DEVICES="-1"` (override with `CUDA_VISIBLE_DEVICES=0 uv run main.py ...` to use GPU)
- PaddleOCR initialized with `lang="japan"`, `use_angle_cls=True` for Japanese text detection
- Image preprocessing: OpenCV resizes short side to 960px, converts to grayscale (cv2.INTER_CUBIC)
- Database: SQLite at `data/db.sqlite3` stores receipts, templates, coordinate corrections

## High-Level Architecture

**System Purpose**: Automated OCR pipeline for medical receipts with human-in-the-loop feedback and clinic-specific template caching. Helps users quickly extract and normalize medical expense data for tax deduction.

**Data Flow** (image → structured output):
```
Receipt image
    ↓
Image preprocessing (resize, grayscale)
    ↓
PaddleOCR (text + bounding box coordinates)
    ↓
LLM structuring (OpenAI/Claude or mock) → structured JSON
    ↓
Coordinate-based template correction (20px proximity threshold)
    ↓
Data normalization (dates, amounts, clinic names)
    ↓
Web UI for human review/correction
    ↓
Database persistence + template learning
```

**Core Components**:

1. **OCR Pipeline** (`app/ocr_pipeline.py`):
   - Wraps PaddleOCR, extracts text and bounding box coordinates
   - Returns list of `(text, bbox)` tuples for each detected region
   - Supports multi-line regions with character-level precision

2. **Image Preprocessing** (`app/image_resize.py`):
   - Resizes short side to 960px, converts to grayscale (cv2.INTER_CUBIC)
   - Outputs prefixed as `resized_gray_{original_name}`
   - Outputs date-stamped OCR JSON: `YYYYMMDD_{image_stem}-raw_data.json`

3. **Service Layer** (`app/services/`):
   - **ReceiptService**: High-level orchestrator for receipt processing pipeline
   - **OCRCoordinateService**: Manages coordinate search, template matching, and field extraction
   - **OCRSearchStrategies**: Strategy-based coordinate search (proximity, text matching, multi-box)
   - **ReceiptDatabaseRepository**: SQLite CRUD (queries, inserts, updates, sync)
   - **ReceiptFileRepository**: File I/O for JSON receipts (load/save)
   - **ReceiptUpdater**: Centralized logic for Web UI PUT endpoint (orchestrates all updates)
   - **ReceiptNormalizer**: Normalizes extracted data (dates, amounts, clinic names)

4. **Coordinate Search & Matching** (`app/coord_search.py`, `app/services/ocr_search_strategies.py`):
   - **Proximity-based search** (20px threshold): Finds OCR coordinates near template coordinates
   - **Multi-box support**: Handles split fields (e.g., name in two text boxes) — returns concatenated text
   - **Text similarity fallback**: String-based matching when proximity doesn't find exact matches
   - Used for template-based extraction and user correction learning

5. **Data Normalization** (`app/normalization.py`):
   - `parse_amount()`: Handles numeric, comma-separated, kanji (一万二千円), plain strings → int/None
   - `parse_date()`: Extracts dates from OCR text, normalizes Japanese era dates (令和N年M月D日 → ISO)
   - `normalize_clinic_name()`: Strips suffixes (病院, クリニック), handles variations
   - All functions are robust to empty/malformed input

6. **LLM Integration** (`app/llm_extractor.py`):
   - Calls external LLM API (OpenAI/Claude via httpx2) to structure OCR results
   - Prompt templates in `app/prompts.py`
   - Identifies clinic names, extracts key fields (date, amount, items)
   - Falls back to MockLLMClient for testing (uses hardcoded mock data)

7. **Structural Parsing** (`app/structural_parser.py`):
   - Parses LLM JSON responses into normalized `Receipt` dataclass
   - Validates required fields, applies coordinate template search
   - Handles errors gracefully (missing fields → None)

8. **Directory Watcher** (`app/watcher.py`):
   - Watchdog observer (inotify on Linux) or polling loop (10s interval)
   - Detects new image files, triggers processing pipeline
   - Outputs structured JSON to `output_json/`
   - CLI: `--watch`, `--use-watchdog`, `--run-once`, `--input-dir`, `--output-dir`

9. **Web UI Server** (`app/web/server.py`):
   - FastAPI application with Jinja2 templates
   - Routes: `GET /` (list receipts), `GET /<file_stem>` (view), `PUT /<file_stem>` (update)
   - Integration with `ReceiptUpdater` for synchronized DB/JSON updates
   - Runs on port 8000 by default

10. **Database** (`app/db.py`, `docs/schema.sql`):
    - SQLite at `data/db.sqlite3` (single file, no server)
    - Tables: `receipts`, `clinic_templates`, `coordinate_corrections`, `feedback_logs`
    - Auto-syncs `clinic_id` when clinic name changes
    - Template coordinates cached per clinic for reuse

**Dataflow (Web UI Update/Correction)**:
```
User edits receipt via Web UI (e.g., fixes clinic name)
       ↓
PUT /<file_stem> endpoint (FastAPI)
       ↓
ReceiptUpdater.update_receipt() orchestrates:
   1. Load JSON (ReceiptFileRepository.load_receipt())
   2. Normalize updates (ReceiptNormalizer.normalize())
   3. Update DB, sync clinic_id (ReceiptDatabaseRepository.update_receipt())
   4. Update coordinate templates (OCRCoordinateService.add_correction())
   5. Save updated JSON (ReceiptFileRepository.save_receipt())
       ↓
Receipt persisted with corrections, templates updated for future extractions
```

**Dataflow (Image Processing)**:
```
input image → image_resize → PaddleOCR (raw OCR data)
    ↓
LLM structuring (or mock) → normalized receipt
    ↓
Template coordinate search (20px proximity) → refine extracted fields
    ↓
Save structured JSON to output_json/, update DB
    ↓
Web UI presents editable receipt for human review
    ↓
User feedback loop (corrections stored as templates)
```

## Key Conventions

1. **Service-Oriented Architecture (SRP)**:
   - `app/services/` contains specialized components, each with a single responsibility
   - Services delegate to repositories for data access, avoiding direct DB calls
   - Coordinate search uses **proximity-first** (20px threshold), falls back to text similarity
   - Multi-box support: Single-box (`List[List[int]]`) and multi-box (`List[List[List[int]]]`) auto-detected

2. **Coordinate System & Multi-Box Support** (new in 2026-07-09):
   - Templates can map fields to single boxes or lists of boxes for split fields
   - Forward path: User correction → `_find_multi_boxes_by_substring()` → template learning
   - Reverse path: Template → `search_fields_by_proximity()` → concatenate boxes by X-coordinate
   - "様" suffix is stripped from concatenated names for cleaner output
   - Backward compatibility: code auto-detects and handles both formats

3. **Database Synchronization**:
   - `clinic_id` is always synced when clinic name changes
   - Template coordinates are cached per clinic for reuse
   - On DB retrieval failure, raw JSON is loaded as fallback
   - Concurrent writes use SQLite's file locking (suitable for single-user/household scenarios)

4. **Argument Handling**:
   - Centralized in `app/args.py` via `setup_args()` and `setup_directories()`
   - Directories auto-created if missing
   - CLI options: `--watch`, `--use-watchdog`, `--input-dir`, `--output-dir`, `--serve`, `--db-path`

5. **Normalization & Parsing**:
   - `parse_amount()` supports: numeric, comma-separated (1,200), kanji (一万二千円), plain strings ("3800" → 3800)
   - Handles Japanese number formats → int; empty/non-numeric → None
   - `parse_date()` extracts dates, normalizes Japanese era dates (令和6年1月1日 → ISO format)
   - `normalize_clinic_name()` strips common suffixes, handles spacing variations
   - All functions robust to None/empty input

6. **Error Handling & Logging**:
   - Centralized logging in `app/error_logging.py`
   - Robust fallbacks for file I/O and DB failures
   - JSON files loaded as backup if DB lookup fails

7. **File Naming Conventions**:
   - OCR JSON: `YYYYMMDD_{image_stem}-raw_data.json` (e.g., `20260710_receipt-raw_data.json`)
   - Resized images: `resized_gray_{original_name}`
   - Database: `data/db.sqlite3`
   - Structured output: `{image_stem}-structured_data.json`

8. **Code Style & Formatting**:
   - Use Black (line-length 119) before commits — non-negotiable
   - Type hints recommended (`from __future__ import annotations` for forward refs)
   - Google-style docstrings with `Args:` / `Returns:`
   - Imports: standard lib → third-party → local; absolute imports preferred
   - Config in `pyproject.toml`

9. **Testing Conventions**:
   - Unit tests in `tests/test_*.py` cover individual functions (normalization, parsing, coordinate search)
   - Integration tests use real DB/fixtures, mock LLM only
   - E2E tests in `tasks/issue_N/` validate end-to-end pipelines
   - Run targeted tests with `pytest -k <pattern>` to speed up development

## Files to Read First

When starting work on this codebase, prioritize these files to understand the flow:

1. **`main.py`** - Entrypoint: CLI argument dispatch, watcher initialization, Web UI server startup
2. **`app/args.py`** - CLI argument definitions, directory setup, CUDA environment configuration
3. **`app/ocr_pipeline.py`** - PaddleOCR integration, coordinate extraction from raw OCR
4. **`app/image_resize.py`** - Image preprocessing (resizing, grayscale conversion)
5. **`app/services/receipt_updater.py`** - Orchestration logic for Web UI PUT endpoint updates
6. **`app/services/ocr_coordinate_service.py`** - Template search, proximity matching, multi-box support
7. **`app/coord_search.py`** - Core coordinate matching algorithms (proximity, text similarity, multi-box)
8. **`app/normalization.py`** - Data parsing (amounts, dates, clinic names — handles Japanese formats)
9. **`app/llm_extractor.py`** - LLM API interface (OpenAI/Claude) for structuring OCR results
10. **`app/web/server.py`** - FastAPI Web UI routes and templates
11. **`pyproject.toml`** - Dependencies and Black configuration
12. **`docs/schema.sql`** - Database schema (tables, relationships)
13. **`要件定義書.md`** - Product requirements and feature roadmap (in Japanese)
14. **`docs/architecture/2026-07-09-architecture.md`** - Latest architectural changes (multi-box support)

## Testing Strategy

- **Unit tests**: `tests/test_*.py` cover individual functions (normalization, parsing, coordinate search)
  - Example: `tests/test_normalization.py` tests `parse_amount()`, `parse_date()`, etc.
- **Integration tests**: `tests/test_watcher_integration.py`, `tests/test_e2e_structured_outputs.py`
  - These use real DB/JSON files, mock LLM only
  - Validate end-to-end pipeline (OCR → structuring → normalization)
- **Web UI tests**: `tests/test_web.py` validates PUT endpoint and `ReceiptUpdater` orchestration
- **E2E tests**: `tasks/issue_4/run_e2e.py` runs mock-based end-to-end validation

**Running tests effectively**:
- Use `pytest -k <pattern>` to run targeted tests quickly during development
- Run full suite (`pytest -q`) before committing
- Use `-v` flag for verbose output when debugging failures

## Recent Architectural Changes (2026-07-09)

- **Multi-box Coordinate Support**: Fields can now be mapped to multiple text boxes (for split fields)
  - Forward: User correction → `_find_multi_boxes_by_substring()` → template learning
  - Reverse: Template → `search_fields_by_proximity()` → concatenate by X-coordinate
  - Backward compatible: auto-detects single vs. multi-box format
  - See `tests/test_coord_search.py` for examples
- **Service Layer Stability**: `OCRCoordinateService` refactored into strategy-based search
- **See detailed snapshot**: `docs/architecture/2026-07-09-architecture.md`

## MCP Server Setup

**Recommended MCP Servers** (optional, for enhanced Copilot integration):

1. **MCP File Server**:
   - Enables Copilot to browse and understand repository structure efficiently
   - Useful for: Large-context code analysis, architecture review, documentation generation

2. **LLM API Integration** (for development/testing):
   - `app/llm_extractor.py` calls external LLM APIs (OpenAI/Claude)
   - Configure via environment variables: `OPENAI_API_KEY`, `CLAUDE_API_KEY`, etc.
   - No MCP required — uses standard HTTP clients (`httpx2`)

**Note**: MCP servers are configured in your IDE/Copilot CLI settings, not in this repository.

## Common Development Workflows

**Adding a new field to receipt extraction**:
1. Update `Receipt` dataclass in `app/structural_parser.py` if needed
2. Update LLM prompt in `app/prompts.py` to extract the field
3. Add parsing logic to `app/normalization.py` (or use existing parser)
4. Write unit tests in `tests/test_normalization.py`
5. Test with `pytest tests/test_normalization.py -v`
6. Format with `black app/normalization.py app/structural_parser.py`

**Fixing coordinate search issues**:
1. Check test case in `tests/test_coord_search.py` (add if missing)
2. Review `app/coord_search.py` for proximity/text matching logic
3. Consider multi-box case: `List[List[List[int]]]` vs single-box `List[List[int]]`
4. Run targeted test: `pytest tests/test_coord_search.py::test_name -v`
5. Update templates in DB if behavior changes: `python -m app.db_migrations ...`

**Improving date/amount parsing**:
1. Add edge case test in `tests/test_normalization.py`
2. Update parsing logic in `app/normalization.py`
3. Run tests: `pytest tests/test_normalization.py -v`
4. Check integration with `app/structural_parser.py` if needed
5. Format: `black app/normalization.py`

## Troubleshooting

**"database is locked" error**:
- SQLite limitation: multiple concurrent writers cause locks
- Typical solution: close any other connections or processes accessing `data/db.sqlite3`
- For production: consider adding write queue or timeout retry logic

**"No module named 'paddleocr'" after setup**:
- Re-run: `uv add --editable .` to ensure all dependencies installed
- Check Python version: `python --version` (must be ≥3.11)
- Verify venv is activated: `source .venv/bin/activate`

**PaddleOCR downloads large models on first run**:
- First run downloads ~500MB model files to `~/.paddleocr/`
- Expect 1-2 minutes for first image processing
- Subsequent runs use cached models (fast)

**OCR coordinates seem off**:
- Check that image was resized correctly: `ls -la resized_gray_*`
- Verify coordinates are in resized image space, not original image
- Use `app/coord_search.py` proximity tests to validate matching logic
