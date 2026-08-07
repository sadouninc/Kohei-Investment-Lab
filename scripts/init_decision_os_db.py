#!/usr/bin/env python3
"""Initialize or migrate the local Investment Decision OS SQLite database.

The database itself lives under data/database/ and is intentionally ignored by
Git. Only migration SQL and code are version controlled.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "database" / "investment.db"
MIGRATIONS = ROOT / "database" / "migrations"


def ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def migration_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.sql") if path.is_file())


def applied_versions(connection: sqlite3.Connection) -> set[str]:
    ensure_migration_table(connection)
    return {
        str(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations")
    }


def apply_migrations(db_path: Path, migration_dir: Path = MIGRATIONS) -> list[str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    applied_now: list[str] = []

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        already_applied = applied_versions(connection)

        for migration in migration_files(migration_dir):
            version = migration.stem.split("_", 1)[0]
            if version in already_applied:
                continue

            sql = migration.read_text(encoding="utf-8")
            try:
                connection.executescript(sql)
                connection.execute(
                    "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                    (version, migration.name),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

            applied_now.append(migration.name)
            already_applied.add(version)

    return applied_now


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply Investment Decision OS SQLite migrations."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--migrations",
        type=Path,
        default=MIGRATIONS,
        help="Migration directory.",
    )
    args = parser.parse_args()

    applied = apply_migrations(args.db, args.migrations)
    if applied:
        print("Applied migrations:")
        for name in applied:
            print(f"- {name}")
    else:
        print("Database schema is already up to date.")
    print(f"Database: {args.db}")


if __name__ == "__main__":
    main()
