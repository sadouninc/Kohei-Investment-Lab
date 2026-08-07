PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decision_securities (
    security_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    exchange TEXT,
    sector TEXT,
    currency TEXT NOT NULL DEFAULT 'JPY',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decision_themes (
    theme_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decision_security_themes (
    security_code TEXT NOT NULL,
    theme_id TEXT NOT NULL,
    role TEXT,
    weight REAL,
    valid_from TEXT NOT NULL DEFAULT (date('now')),
    valid_to TEXT,
    PRIMARY KEY (security_code, theme_id, valid_from),
    FOREIGN KEY (security_code) REFERENCES decision_securities(security_code),
    FOREIGN KEY (theme_id) REFERENCES decision_themes(theme_id)
);

CREATE TABLE IF NOT EXISTS universe_membership (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE','WATCH','RESEARCH','WAITING','REMOVE_CANDIDATE')),
    priority TEXT CHECK (priority IS NULL OR priority IN ('HIGH','MEDIUM','LOW')),
    reason TEXT,
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    source_commit TEXT,
    FOREIGN KEY (security_code) REFERENCES decision_securities(security_code)
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT,
    config_json TEXT,
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    source_commit TEXT,
    UNIQUE(model_name, version)
);

CREATE TABLE IF NOT EXISTS routine_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT,
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    source_commit TEXT,
    UNIQUE(routine_name, version)
);

CREATE TABLE IF NOT EXISTS framework_metadata (
    framework_key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_path TEXT NOT NULL,
    version TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    source_commit TEXT
);

CREATE INDEX IF NOT EXISTS idx_universe_membership_time
ON universe_membership(security_code, valid_from, valid_to);
