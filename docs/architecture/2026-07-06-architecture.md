# Architecture Snapshot - 2026-07-06

## Purpose
This snapshot documents significant refactoring and architectural adjustments currently present in the working directory (uncommitted). The primary focus is on strengthening the service layer (SRP) and improving data handling, specifically regarding coordinate correction, database repository interaction, and template feedback mechanisms.

## Overview
- **Core Components Changed**:
    - `app/services/ocr_coordinate_service.py`: Significant expansion of coordinate handling logic.
    - `app/services/receipt_database_repository.py`: Newly created/updated repository to centralize DB interactions.
    - `app/services/receipt_updater.py`: Refactored to delegate responsibilities to the new repository and coordinate service, simplifying its internal logic.
    - `app/web/templates/detail.html`: Updated UI to support enhanced template feedback.
    - `app/normalization.py`: Refined normalization logic.

## Key Design Decisions
- **Service Layer Consolidation**: Moved complex coordinate search logic out of `receipt_updater` into the specialized `ocr_coordinate_service`.
- **Repository Pattern**: Formalized `receipt_database_repository` to isolate persistence logic, reducing direct dependency on SQLAlchemy/SQLite in the service layer.
- **Improved Testing**: Added comprehensive unit tests for new service-layer logic in `test_db.py`, `test_feedback.py`, and `test_normalization.py` to ensure structural integrity post-refactoring.

## Changed Files (Uncommitted)
- `QWEN.md`
- `app/db.py`
- `app/image_resize.py`
- `app/normalization.py`
- `app/services/ocr_coordinate_service.py`
- `app/services/receipt_database_repository.py`
- `app/services/receipt_updater.py`
- `app/structural_parser.py`
- `app/web/templates/detail.html`
- `tests/test_coord_search.py`
- `tests/test_db.py`
- `tests/test_feedback.py`
- `tests/test_image_resize.py`
- `tests/test_normalization.py`
- `tests/test_structural_parser.py`
- `tests/test_watcher_integration.py`
- `tests/test_web.py`
