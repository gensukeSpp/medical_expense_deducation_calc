# 2026-07-03 Architecture snapshot

## Purpose
Document the architectural refactoring of `ReceiptService` and the implementation of Issue #26 fixes to improve data consistency and robustness in the Web UI processing flow.

## Overview
- **Service-Oriented Refactoring**: `ReceiptService` has been refactored into an orchestrator that delegates responsibilities to specialized components, improving testability and maintainability.
- **Robustness & Consistency**: Addressed issues with plain number parsing, DB/JSON data synchronization (especially `clinic_id` updates), and robust template data ingestion.

## Key Components Changed
- `app/services/receipt_service.py`: Orchestrator refactoring (delegation).
- `app/services/receipt_updater.py`: Centralized update logic and orchestration.
- `app/services/receipt_database_repository.py`: DB operations.
- `app/services/receipt_file_repository.py`: File I/O operations.
- `app/normalization.py`: Added support for plain numeric strings in `parse_amount`.
- `app/watcher.py`: Consolidated argument definition.

## Dataflow (Web UI Update)
1. `PUT /<file_stem>` triggered.
2. `ReceiptUpdater.update_receipt` orchestrates:
    - Load JSON via `ReceiptFileRepository`.
    - Normalize updates via `ReceiptNormalizer`.
    - Update DB (Corrections, `clinic_id` sync) via `ReceiptDatabaseRepository`.
    - Coordinate feedback & template update via `OCRCoordinateService`.
    - Save updated JSON via `ReceiptFileRepository`.

## Key Design Decisions
- **SRP Implementation**: Distributed responsibilities of the formerly monolithic `ReceiptService` to dedicated repository and service classes.
- **Robust Fallbacks**: Improved OCR data ingestion by adding direct raw JSON reading as a fallback when DB retrieval fails.
- **Coordinate Search Strategy**: Prioritize proximity-based search (`search_by_proximity_multi`) when template coordinates exist, falling back to string similarity (`search_coordinates`) otherwise.

## Next Steps
- Monitor Web UI stability with the new orchestration layer.
- Plan for future RealLLMClient integration using the new service-oriented structure.

## Changed Files
- app/normalization.py
- app/services/receipt_service.py
- app/services/ocr_coordinate_service.py
- app/services/receipt_database_repository.py
- app/services/receipt_file_repository.py
- app/services/receipt_normalizer.py
- app/services/receipt_updater.py
- app/watcher.py
- tests/test_normalization.py
- tests/test_web.py
