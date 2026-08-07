PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS market_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    source TEXT NOT NULL,
    source_timestamp TEXT,
    ingestion_version TEXT,
    UNIQUE(symbol, timeframe, observed_at, source)
);

CREATE TABLE IF NOT EXISTS security_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    turnover REAL,
    source TEXT NOT NULL,
    ingestion_version TEXT,
    UNIQUE(security_code, timeframe, observed_at, source)
);

CREATE TABLE IF NOT EXISTS order_book_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intraday_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    feature_set TEXT NOT NULL,
    features_json TEXT NOT NULL,
    model_version TEXT,
    UNIQUE(security_code, generated_at, timeframe, feature_set)
);

CREATE TABLE IF NOT EXISTS analysis_cache (
    cache_key TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    expires_at TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_observations_symbol_time
ON market_observations(symbol, timeframe, observed_at);
CREATE INDEX IF NOT EXISTS idx_security_observations_code_time
ON security_observations(security_code, timeframe, observed_at);
CREATE INDEX IF NOT EXISTS idx_order_book_code_time
ON order_book_snapshots(security_code, observed_at);
CREATE INDEX IF NOT EXISTS idx_features_code_time
ON intraday_features(security_code, timeframe, generated_at);
