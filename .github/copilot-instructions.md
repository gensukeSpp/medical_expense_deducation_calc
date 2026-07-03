# Copilot Instructions for medical-exp-deducation-calc

## Purpose

Guidance for Copilot sessions to efficiently work in this medical expense deduction calculator codebase—how to build, test, run, lint, and understand the system architecture.

## Build, Test, and Lint

**Python Version**: ≥ 3.11 (see `pyproject.toml`)

**Setup**:
```bash
python -m venv .venv
source .venv/bin/activate
uv pip install --upgrade uv[all]
uv add --editable .  # Install project dependencies from pyproject.toml
```

**Running the Application**:
```bash
# Watch mode: monitors input directory and processes receipts automatically
python main.py --watch --input-dir ~/Downloads/receipts --output-dir output_json

# Single image processing via CLI
python main.py --input-json path/to/ocr_data.json --model <model_name> --db-path data/db.sqlite3

# Setup database schema (required on first run)
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
```

**Linting & Formatting**:
```bash
# Format entire project
black .

# Format specific file
black path/to/file.py

# Configuration: pyproject.toml, line-length = 119
```

**Notes**:
- CPU-first default: `CUDA_VISIBLE_DEVICES="-1"` in `main.py` (override to enable GPU)
- Language: PaddleOCR initialized with `lang="japan"`
- Image preprocessing: cv2.INTER_CUBIC resizing, grayscale conversion
- Database: SQLite at `data/db.sqlite3` (requires initialization via `db_migrations`)

## High-Level Architecture

**System Purpose**: Automated OCR pipeline for medical receipts with human-in-the-loop feedback and clinic-specific template caching.

**Core Components**:

1. **OCR Pipeline** (`app/ocr_pipeline.py`):
   - Wraps PaddleOCR, extracts text and bounding box coordinates
   - Initializes with `lang="japan"`, `use_angle_cls=True`

2. **Image Preprocessing** (`app/image_resize.py`):
   - Resizes short side to 960px, converts to grayscale
   - Outputs prefixed as `resized_gray_{original_name}`

3. **Service Layer** (`app/services/`):
   - **ReceiptService**: Orchestrator for receipt processing
   - **OCRCoordinateService**: Manages coordinate-based corrections and template search
   - **ReceiptDatabaseRepository**: DB operations (queries, inserts, updates)
   - **ReceiptFileRepository**: File I/O for JSON receipts
   - **ReceiptUpdater**: Centralized update logic for Web UI operations
   - **ReceiptNormalizer**: Normalizes extracted data (dates, amounts, clinic names)

4. **Data Normalization** (`app/normalization.py`):
   - `parse_amount()`: Handles numeric, comma-separated, kanji, and plain numeric strings
   - `parse_date()`: Extracts and normalizes dates
   - Handles Japanese era dates (元号)

5. **LLM Integration** (`app/llm_extractor.py`):
   - Calls external LLM (OpenAI/Claude) to structure OCR results
   - Identifies clinic names and extracts key fields (date, amount, items)

6. **Structural Parsing** (`app/structural_parser.py`):
   - Parses LLM JSON responses into normalized receipt format
   - Validates and extracts corrections

7. **Directory Watcher** (`app/watcher.py`):
   - Polling or watchdog-based monitoring of input directory
   - Processes receipts and coordinates feedback loop
   - CLI: `--watch`, `--use-watchdog`, `--run-once`, `--input-dir`, `--output-dir`

8. **Database** (`app/db.py`, `docs/schema.sql`):
   - Stores receipts, clinic templates, coordinate offsets, user corrections
   - Tables: `receipts`, `clinic_templates`, `coordinate_corrections`, `feedback_logs`

**Dataflow (Web UI Update)**:
```
User edits receipt via Web UI
       ↓
PUT /<file_stem> endpoint
       ↓
ReceiptUpdater.update_receipt orchestrates:
   1. Load JSON (ReceiptFileRepository)
   2. Normalize updates (ReceiptNormalizer)
   3. Update DB, sync clinic_id (ReceiptDatabaseRepository)
   4. Update coordinate templates (OCRCoordinateService)
   5. Save updated JSON (ReceiptFileRepository)
       ↓
Receipt persisted with corrections, templates updated
```

**Dataflow (Image Processing)**:
```
input image → image_resize → PaddleOCR → normalize → LLM structuring
    ↓                                                          ↓
save to output_json, update DB                    Web UI shows editable receipt
                                                            ↓
                                                   User feedback loop
```

## Key Conventions

1. **Service-Oriented Architecture (SRP)**:
   - `app/services/` contains specialized components with single responsibilities
   - Services delegate to repositories for data access
   - Coordinate search prioritizes proximity-based matching (20px threshold) before string similarity fallback

2. **Database Synchronization**:
   - `clinic_id` is always synced when clinic name changes
   - Template coordinates are cached per clinic for reuse
   - On DB retrieval failure, raw JSON is loaded as fallback

3. **Argument Handling**:
   - Centralized in `app/args.py` via `setup_args()` and `setup_directories()`
   - Directories auto-created if missing

4. **Normalization**:
   - `parse_amount()` supports: numeric, comma-separated, kanji, plain strings (e.g., "3800" → 3800)
   - Handles Japanese number formats (一万二千円 → 12000)
   - Empty/non-numeric strings return `None`

5. **Error Handling**:
   - Centralized logging in `app/error_logging.py`
   - Robust fallbacks for file I/O and DB failures

6. **File Naming**:
   - OCR JSON: `YYYYMMDD_{image_stem}-raw_data.json`
   - Resized images: `resized_gray_{original_name}`
   - Database: `data/db.sqlite3`

7. **Formatting**:
   - Use Black (line-length 119) before commits
   - Linting config in `pyproject.toml`

## Files to Read First

- **`main.py`** - Entrypoint, argument setup, watcher initialization
- **`app/args.py`** - CLI argument definitions and directory setup
- **`app/services/receipt_updater.py`** - Orchestration logic for updates
- **`app/ocr_pipeline.py`** - PaddleOCR integration
- **`app/normalization.py`** - Data parsing (amounts, dates, clinic names)
- **`pyproject.toml`** - Dependencies and Black configuration
- **`docs/schema.sql`** - Database schema
- **`要件定義書.md`** - Product requirements and feature roadmap (Japanese)

## Testing Strategy

- **Unit tests**: `tests/test_*.py` cover individual functions (normalization, parsing, coordinate search)
- **Integration tests**: `tests/test_watcher_integration.py`, `tests/test_e2e_structured_outputs.py`
- **Web UI tests**: `tests/test_web.py` validates PUT endpoint and orchestration
- Run targeted tests with `pytest -k <pattern>` to speed up development

## Recent Architectural Changes (2026-07-03)

- **SRP Refactoring**: `ReceiptService` decomposed into `ReceiptUpdater`, repositories, and specialized services
- **Robustness Fixes**: Plain numeric parsing in `parse_amount()`, DB/JSON sync for `clinic_id`, raw JSON fallback
- **Coordinate Strategy**: Prioritize proximity search (20px) over string similarity for clinic-specific templates
- See `docs/architecture/2026-07-03-architecture.md` for detailed snapshot

## MCP Server Setup

**Recommended MCP Servers** (optional, for enhanced IDE/LLM support):

1. **MCP File Server**:
   - Enables Claude/other LLMs to browse and understand the repository structure
   - Configuration: Refer to your Copilot CLI or Claude documentation
   - Useful for: Large-context code analysis, architecture review, documentation generation

2. **LLM API Integration** (for local development):
   - `app/llm_extractor.py` calls external LLM APIs (OpenAI/Claude)
   - Configure via environment variables: `OPENAI_API_KEY`, `CLAUDE_API_KEY`, etc.
   - No MCP required—uses standard HTTP clients (`httpx2`)

**Note**: MCP servers are configured in your development environment/IDE settings, not in this repository.
