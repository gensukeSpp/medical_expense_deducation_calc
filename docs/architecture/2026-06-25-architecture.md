# Architecture Snapshot: 2026-06-25

## Purpose
Document the current architecture of the Medical Expense Deduction Calculator, covering the OCR pipeline, LLM integration, database persistence, and Web UI.

## Overview
The application is a Python-based OCR tool that processes medical receipts to extract and normalize data for tax deductions. It utilizes PaddleOCR for text detection, local LLM/heuristic-based extraction for data structuring, and SQLite for persistence. A FastAPI-based Web UI enables human-in-the-loop corrections.

## Core Components
- **OCR Pipeline (`app/ocr_pipeline.py`)**: Handles image preprocessing (`app/image_resize.py`) and PaddleOCR inference.
- **LLM/Heuristic Extractor (`app/llm_extractor.py`)**: Extracts raw fields from OCR text lines.
- **Normalization (`app/normalization.py`)**: Sanitizes and formats extracted fields (dates, amounts).
- **Data Persistence (`app/db.py`)**: Manages SQLite database interactions, including receipt storage, clinic templates, and user corrections.
- **Web UI (`app/web/server.py`)**: FastAPI application for data review and manual correction of OCR results, interacting directly with JSON outputs and the SQLite database.

## Dataflow
1. **Input**: Images are monitored/scanned from the input directory.
2. **Processing**: Images are resized -> OCR'd -> Structured/Normalized via LLM/Heuristics -> Saved as JSON.
3. **Persistence**: Structured results and corrections are optionally stored in SQLite.
4. **Correction**: Users review/edit JSON results via Web UI, updating the JSON file and the SQLite database simultaneously.

## Design Decisions
- **Human-in-the-Loop**: Prioritized Web UI for reviewing and correcting extracted JSON data.
- **Data Integrity**: Used atomic JSON writes and transaction-managed SQLite operations to prevent corruption.
- **Separation of Concerns**: Decoupled processing logic (OCR, normalization) from management logic (DB, UI).

## Next Steps
- Implement full automated test coverage for Web UI interactions with DB.
- Explore integration with a real LLM API provider beyond the `mock` client.
