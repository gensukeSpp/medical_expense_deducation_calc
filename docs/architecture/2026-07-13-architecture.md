# Architecture Snapshot - 2026-07-13

## Purpose
Refactoring the receipt management system to enforce Single Responsibility Principle (SRP) and improve modularity through a service-based orchestration pattern, and implementing relative coordinate calculation to improve robustness against photography offsets.

## Overview
- **Key Shifts**:
  - Moved receipt update logic from `ReceiptService` into a dedicated `ReceiptUpdater` component.
  - Introduced relative coordinate normalization to handle document layout variations.
- **Core Components Changed**:
  - `ReceiptService`: Acts as an orchestrator delegating update operations to `ReceiptUpdater`.
  - `ReceiptUpdater`: Centralized logic for coordinate corrections, database persistence, and file updates; now includes gating logic for template updates based on OCR confidence.
  - `ReceiptDatabaseRepository`: Refined for consistent persistence.
  - `app/processor.py` & `app/watcher.py`: Updated to interface with new service orchestration and coordinate normalization.

## Key Design Decisions
- **Orchestration Pattern**: `ReceiptService` provides a high-level API; internal orchestration of complex update workflows (including gating) is handled by `ReceiptUpdater` to reduce coupling.
- **Coordinate Normalization**: Implemented `normalize_coordinates()` to convert raw absolute box coordinates to relative coordinates (top-left origin).
- **Proximity Threshold**: Increased from 20px to **50px** to balance matching sensitivity and robustness against residual offsets after relative normalization.
- **Confidence Gating**: Low-confidence OCR results (< 0.8) trigger coordinate relative normalization to be skipped, flagging `low_confidence: true` in the output, and gating automatic template updates to prevent polluting coordinate databases.

## Next Steps
- Continue increasing unit test coverage for `ReceiptUpdater`, `ReceiptDatabaseRepository`, and coordinate normalization logic.

## Commits
- (Uncommitted changes currently in the working tree)

## Changed Files
- app/processor.py
- app/services/receipt_database_repository.py
- app/services/receipt_service.py
- app/services/receipt_updater.py
- app/structural_parser.py
- app/watcher.py
- app/web/templates/index.html
- tests/test_coordinate_service.py
- tests/test_structural_parser.py
- tests/test_web.py
