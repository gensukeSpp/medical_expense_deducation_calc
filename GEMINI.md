# Project: Medical Expense Deduction Calculator

This project is an automated OCR application designed to streamline the extraction and management of data from medical receipts for tax deduction purposes.

## Project Overview

The primary goal is to simplify data entry for medical expenses within a household. It follows a "Human-in-the-Loop" design, allowing the system to learn from user corrections to improve OCR accuracy over time, specifically for clinic-specific document layouts.

## Architecture & Technologies

- **Language**: Python (>=3.11)
- **OCR Engine**: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) (for text and coordinate extraction)
- **Image Processing**: OpenCV
- **LLM Components**:
    - **Structural LLM**: Extracted text from OCR is formatted into a structured JSON representation (date, amount, items, etc.).
    - **Naming Extractor LLM**: Identifies and extracts the clinic name from raw OCR text.
- **Data Management** (Planned):
    - **SQLite**: Local database (`data/db.sqlite3`) to store receipts, clinic templates, coordinate correction offsets, and user modifications.

## Key Files & Directories

- `main.py`: Main entry point integrating the directory watcher, OCR pipeline, and LLM processing.
- `app/`: Contains core application logic.
    - `app/ocr_pipeline.py`: Logic for PaddleOCR-based text and coordinate extraction.
    - `app/image_resize.py`: Image pre-processing utilities (resizing, scaling).
    - `app/watcher.py`: Directory watcher tracking incoming receipts and triggering processing.
    - `app/llm_extractor.py`: Handles interfacing with the LLM API for extraction.
    - `app/structural_parser.py`: Parses the LLM structural outputs.
    - `app/normalization.py`: Normalizes text, amounts, dates, and clinic names.
    - `app/error_logging.py`: Centralized error logging utility.
- `tasks/`:
    - `tasks/issue_4/run_e2e.py`: E2E test runner validating the extraction output.
    - `tasks/issue_18/ISSUE_18.md`: Task definition for implementing SQLite database storage.
- `tests/`: Contains Unit and E2E test suites.
- `要件定義書.md`: Core system requirements and functional specifications (Japanese).
- `pyproject.toml`: Project configuration and dependency specifications.

## Running the Application

Ensure your environment is set up (see `pyproject.toml`).

### Start the Directory Watcher:
```bash
python main.py
```

### Process an OCR JSON file directly (CLI Mode):
```bash
python main.py --input-json <path_to_ocr_json> --model <model_name>
```

### Run E2E Tests:
```bash
python tasks/issue_4/run_e2e.py
```

## Current Progress & Upcoming Tasks

### Implemented Features (as of 2026-06-18)
- Complete pipeline integration (OCR + LLM Extraction + Normalization).
- CLI integration for model and input JSON file configuration.
- Robust date, clinic name, and monetary value normalization.
- E2E testing framework with mockup validations.

### Upcoming Tasks
- **Issue 18: SQLite Database Persistence**
  - Implement SQLite database schema (`data/db.sqlite3`) for storing receipts, clinics, templates, and corrections.
  - Implement SQLite connection and CRUD API in `app/db.py`.
  - Integrate database persistence in `app/structural_parser.py` and `main.py`.
  - Provide database migration scripts in `app/db_migrations.py` or similar setup tools.

## Development Conventions

- **Type Safety**: Use type hints where appropriate.
- **Code Style**: Adhere to PEP 8 standards. Use `black` for formatting (line length 119).
- **Docstrings**: All functions should include descriptive docstrings detailing parameters and purpose.
- **Modularity**: Maintain clean separation between processing logic (OCR, resizing) and management logic (data persistence).
- **Security**: Never hardcode credentials, paths, or sensitive data. Use environment variables for configuration.

