# 2026-06-19 Architecture snapshot

Date: 2026-06-19

Purpose
- Snapshot capturing the architectural progression toward implementing SQLite database persistence for medical receipt processing.

Overview
- Purpose: Augment the existing OCR-to-LLM pipeline with persistent storage for receipts, clinic templates, and user-corrected data.
- Key shifts: Integration of SQLite for data management, enabling structured storage of extraction results and facilitating "Human-in-the-Loop" corrections.

Core components (relevant to recent changes)
- app/structural_parser.py
  - Orchestrates interaction between LLM output parsing and database persistence.
- app/normalization.py
  - Refined normalization logic to support database insertion requirements.
- main.py
  - Updated CLI entry point to reflect new persistence capabilities.

Dataflow
- Input image -> OCR -> LLM -> Structural Parsing -> (New) SQLite Database persistence.

Key design decisions
- Use of SQLite for local persistence (data/db.sqlite3).
- Structured storage of receipts, clinic-specific templates, and extracted metadata.

Next steps / improvements
- Fully implement CRUD API in app/db.py.
- Complete database migration scripts in app/db_migrations.py.
- Integrate database persistence fully into the OCR processing pipeline.

Commits (origin/main..HEAD)
---------------------------
- c467adb docs #260619: 今後の予定:  データベース機能

Changed Python files
--------------------
- app/args.py
- app/normalization.py
- app/structural_parser.py
- main.py

(End of snapshot)
