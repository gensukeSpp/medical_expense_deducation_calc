# Architecture Update: 2026-07-16

## Purpose
Document the implementation of Hybrid template key matching for robust OCR data extraction (Issue #34).

## Overview
- **Hybrid Template Key Matching**: Implemented a 3-stage fallback mechanism for clinic template matching (Exact Name Match, Text Similarity, Layout-based Matching). This significantly improves robustness against OCR character recognition errors and name extraction failures.
- **SRP Refactoring**: This update continues the ongoing architectural effort to decouple business logic from orchestrator components.

## Key Design Decisions
- **Fallback Strategy**:
  1. Exact Name Match (Existing)
  2. Text Similarity (using `difflib` with 0.6 threshold)
  3. Layout-based Matching (using 50px proximity threshold and 60% field match ratio)
- **Database Enhancement**: Added `get_all_clinics()` and `get_all_templates_with_names()` to support the fallback search strategy.

## Changed Files
- `QWEN.md`
- `app/coord_search.py`
- `app/db.py`
- `app/structural_parser.py`
- `tests/test_coord_search.py`
- `tests/test_db.py`
- `tests/test_structural_parser.py`

## Commits
- 2ec251f Merge pull request #33 from gensukeSpp/feature/relative-coords-calculation/32
- ... (Additional work leading up to current state)
