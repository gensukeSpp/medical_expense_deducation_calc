# Architecture Snapshot - 2026-07-13

## Purpose
Refactoring the receipt management system to enforce Single Responsibility Principle (SRP) and improve modularity through a service-based orchestration pattern.

## Overview
- **Key Shifts**: Moved receipt update logic from `ReceiptService` into a dedicated `ReceiptUpdater` component.
- **Core Components Changed**:
  - `ReceiptService`: Now acts as an orchestrator delegating update operations to `ReceiptUpdater`.
  - `ReceiptUpdater`: Centralized logic for coordinate corrections, database persistence, and file updates.
  - `ReceiptDatabaseRepository`: Refined to handle persistence more consistently.
  - `app/processor.py` & `app/watcher.py`: Updated to interface with the new service orchestration.

## Key Design Decisions
- **Orchestration Pattern**: `ReceiptService` provides a high-level API for the UI/CLI, while internal orchestration of complex update workflows is handled by `ReceiptUpdater` to reduce coupling in the service layer.

## Next Steps
- Continue increasing unit test coverage for `ReceiptUpdater` and `ReceiptDatabaseRepository`.

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
