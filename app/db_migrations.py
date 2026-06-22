"""Database migration and initialization tool."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from .db import get_db_connection

DEFAULT_DB_PATH = "data/db.sqlite3"
DEFAULT_SCHEMA_PATH = "docs/schema.sql"


def run_migrations(db_path: str | Path, schema_path: str | Path) -> None:
    """Read the SQL schema file and initialize the database.

    Args:
        db_path: Path to the SQLite database file.
        schema_path: Path to the SQL schema file.
    """
    db_path = Path(db_path)
    schema_path = Path(schema_path)

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema SQL file not found at {schema_path}")

    print(f"Initializing database at: {db_path} using schema: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # executescript handles multiple statements and commits implicitly
    conn = get_db_connection(db_path)
    try:
        conn.executescript(schema_sql)
    finally:
        conn.close()
    print("Database initialization complete.")


def main() -> None:
    """CLI entry point for database migrations."""
    parser = argparse.ArgumentParser(description="Database migration and setup utility")
    parser.add_argument("action", choices=["init"], help="Action to perform (e.g., 'init')")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to the SQLite database file")
    parser.add_argument("--schema-path", default=DEFAULT_SCHEMA_PATH, help="Path to the schema SQL file")

    # Use sys.argv directly to handle subcommands simply
    args = parser.parse_args()

    if args.action == "init":
        try:
            run_migrations(args.db_path, args.schema_path)
        except Exception as e:
            print(f"Database initialization failed: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
