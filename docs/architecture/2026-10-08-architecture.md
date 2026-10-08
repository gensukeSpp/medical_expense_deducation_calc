# Architecture Snapshot: 2026-10-08 (Issue #39)

## Purpose
Document the implementation of date-based coordinate normalization (Issue #39), upgrading the receipt OCR pipeline from global topmost/leftmost coordinate normalization to precise date-anchor-based relative normalization using learned clinic templates.

## Overview
- **Date Anchor Resolution**: Resolves the structured receipt date to the specific OCR box that produced it, using the clinic's template date coordinates as a positional hint.
- **Anchor-Based Coordinate Normalization**: When a reliable unique anchor box is found, raw OCR coordinates and stored DB coordinates are re-normalized relative to that date box's top-left corner (`(0, 0)`).
- **Template Basis Migration & History**: Automatically transitions clinic template coordinate basis from `topmost` to `date` upon successful anchor resolution, transactionally saving pre-migration snapshots in `template_history`.
- **Database Schema & Migration**: Added `coord_basis` column to the `templates` table with idempotent database migration support.

## Key Components Changed
- `app/date_anchor.py` (New): Implements candidate date resolution (`find_date_candidates`), anchor selection (`resolve_date_anchor`), and orchestration (`apply_date_anchor_normalization`).
- `app/coord_normalizer.py`: Added `normalize_coordinates_by_anchor` (shifts all boxes relative to an anchor box) and `shift_template_coords` (shifts template coordinate dictionaries).
- `app/db.py`: Added `update_template_basis` (transactional basis migration with history snapshotting) and `update_receipt_ocr_json_by_source` (syncs persisted receipt OCR JSON to date-anchor basis).
- `app/db_migrations.py` & `docs/schema.sql`: Added `coord_basis` column to `templates` (`'topmost'` or `'date'`) with idempotent migration logic.
- `app/services/image_processing_service.py` & `app/services/receipt_processor.py`: Integrated date anchor re-normalization into image processing and watcher pipelines for non-low-confidence receipts.

## Key Design Decisions
- **Safe Fallback**: If template date coordinates are unlearned, text matching fails, or multiple candidate boxes create ambiguity, the pipeline gracefully falls back to legacy global topmost/leftmost normalization.
- **Atomic Basis Migration**: Template coordinate migration to date basis and history snapshotting are performed in a single SQLite transaction to prevent partial state corruption.
- **Avoidance of Duplicate Persistence**: Persisted `receipts.ocr_json` is updated directly in place (`update_receipt_ocr_json_by_source`) without re-running structured parsing, avoiding duplicate receipt row insertion.
- **Preservation of Low-Confidence Gating**: Date anchor normalization is gated behind confidence checks (skipped when low-confidence or preprocessing retry applies), maintaining existing robustness guarantees.

## Changed Files
- `app/coord_normalizer.py`
- `app/date_anchor.py`
- `app/db.py`
- `app/db_migrations.py`
- `app/services/image_processing_service.py`
- `app/services/receipt_processor.py`
- `docs/schema.sql`
- `tests/test_coord_normalizer.py`
- `tests/test_image_processing_service.py`

## Commits (origin/main..HEAD)
- a676af1 docs #261008: 仕様・進捗 docs 追加
- d0dd617 feat #39: 日付基準による座標正規化
