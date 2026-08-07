#!/usr/bin/env python3
"""Initialize or migrate the Investment Decision OS SQLite databases.

Storage policy:
- data/database/master.db  : Git-managed research master data
- data/database/history.db : Git-managed accumulated research history
- data/database/analysis.db: local-only high-volume/reproducible analysis data

Migration SQL is split by database under database/migrations/<target>/.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_DIR = ROOT / "data" / "database"
MIGRATIONS_ROOT = ROOT / "database" / "migrations"


@dataclass(frozen=True)
class DatabaseTarget:
    name: str
    filename: str
    git_managed: bool

    @property
    def migration_dir(self) -> Path:
        return MIGRATIONS_ROOT / self.name


TARGETS = {
    "master": DatabaseTarget("master", "master.db", True),
    "history": DatabaseTarget("history", "history.db", True),
    "analysis": DatabaseTarget("analysis", "analysis.db", False),
}


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


def apply_migrations(db_path: Path, migration_dir: Path) -> list[str]:
    """Apply one target's migrations and return migration file names applied now."""
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


def database_path(target: DatabaseTarget, db_dir: Path = DEFAULT_DB_DIR) -> Path:
    return db_dir / target.filename


def migrate_target(target_name: str, db_dir: Path = DEFAULT_DB_DIR) -> tuple[Path, list[str]]:
    target = TARGETS[target_name]
    path = database_path(target, db_dir)
    applied = apply_migrations(path, target.migration_dir)
    return path, applied


def migrate_all(db_dir: Path = DEFAULT_DB_DIR) -> dict[str, tuple[Path, list[str]]]:
    return {name: migrate_target(name, db_dir) for name in TARGETS}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply split Investment Decision OS SQLite migrations."
    )
    parser.add_argument(
        "--target",
        choices=["all", *TARGETS.keys()],
        default="all",
        help="Database to migrate (default: all).",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=DEFAULT_DB_DIR,
        help=f"Database directory (default: {DEFAULT_DB_DIR.relative_to(ROOT)})",
    )
    args = parser.parse_args()

    names = list(TARGETS) if args.target == "all" else [args.target]
    for name in names:
        target = TARGETS[name]
        path, applied = migrate_target(name, args.db_dir)
        policy = "Git-managed" if target.git_managed else "local-only"
        if applied:
            print(f"[{name}] Applied migrations: {', '.join(applied)}")
        else:
            print(f"[{name}] Database schema is already up to date.")
        print(f"[{name}] {policy}: {path}")


if __name__ == "__main__":
    main()
