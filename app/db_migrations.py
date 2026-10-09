"""Database migration and initialization tool."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from .db import get_db_connection

DEFAULT_DB_PATH = "data/db.sqlite3"
DEFAULT_SCHEMA_PATH = "docs/schema.sql"


def _add_coord_basis_column_if_missing(conn) -> None:
    """Idempotently add the templates.coord_basis column on pre-existing databases.

    ``CREATE TABLE IF NOT EXISTS`` does not alter existing tables, so databases
    created before Issue #39 must be migrated with an explicit ALTER TABLE.
    Running this more than once is a no-op.

    Args:
        conn: Open sqlite3 connection (with foreign keys enabled).
    """
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(templates)")}
    if "coord_basis" not in cols:
        conn.execute("ALTER TABLE templates ADD COLUMN coord_basis TEXT NOT NULL DEFAULT 'topmost'")


def run_migrations(db_path: str | Path, schema_path: str | Path) -> None:
    """Read the SQL schema file and initialize the database.

    Schema application and the idempotent coord_basis column migration are
    performed within a single connection / exclusive transaction so that
    concurrent initializers cannot both observe a missing column and then
    race on a duplicate ALTER TABLE (Issue #39 migration safety).

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

    # Single connection + exclusive transaction: schema application and the
    # coord_basis column migration share the write lock, so concurrent
    # initializers serialize and the idempotent ALTER TABLE cannot race.
    conn = get_db_connection(db_path)
    try:
        conn.execute("BEGIN EXCLUSIVE TRANSACTION")
        try:
            conn.executescript(schema_sql)
            _add_coord_basis_column_if_missing(conn)
        except Exception:
            conn.rollback()
            raise
        conn.commit()
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
