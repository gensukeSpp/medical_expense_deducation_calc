# Architecture snapshot: 2026-06-26

## Purpose
Document implementation of SQLite database persistence and coordinate correction feedback loop (Issue #22).

## Overview
This architectural change introduces a robust persistence layer and a feedback mechanism for improving OCR accuracy.
- **SQLite Integration**: Added persistence for receipts, clinics, templates, and corrections using SQLite (`docs/schema.sql`).
- **Coordinate Feedback Loop**: Implemented a workflow where user corrections via the Web UI automatically trigger an update to the clinic's OCR coordinate template (`app/template_feedback.py`).
- **Web UI Enhancement**: Added endpoint for updating normalized data and processing correction feedback (`app/web/server.py`).

## Dataflow
1. User modifies extraction results in the Web UI.
2. Web UI calls PUT endpoint.
3. `app/web/server.py` updates JSON data, records correction in SQLite.
4. `app/template_feedback.py` uses `app/coord_search.py` to find the new coordinates for the corrected field.
5. If found, `app/template_feedback.py` upserts/updates the clinic's coordinate template in SQLite.

## Key Design Decisions
- **Check-then-Act Avoidance**: Used helper functions like `get_or_create_clinic` to handle concurrency during clinic creation.
- **FK Constraints**: Used CASCADE DELETE for templates and corrections associated with receipts.

## Next steps/improvements
- Implement automated retraining based on updated templates.

## Commits
- 34c85e2 Merge pull request #21 from gensukeSpp/feature/db-persistence/20
- 4985759 fix #260625: レビュー対応 #21、バグ修正
- 05a6b63 feat #260625: 抽出データをユーザーが確認・修正する Web UI を実装

## Changed files
- app/db.py
- app/web/server.py
- docs/schema.sql
- app/template_feedback.py
- app/coord_search.py
