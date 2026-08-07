PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS investor_environment_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment_key TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    expected_check_interval_minutes INTEGER,
    market_open_monitoring TEXT NOT NULL DEFAULT 'UNKNOWN',
    morning_execution_availability TEXT NOT NULL DEFAULT 'UNKNOWN',
    network_reliability TEXT NOT NULL DEFAULT 'UNKNOWN',
    fast_reaction_capability TEXT NOT NULL DEFAULT 'UNKNOWN',
    premarket_analysis_availability TEXT NOT NULL DEFAULT 'UNKNOWN',
    work_constraint_level TEXT NOT NULL DEFAULT 'UNKNOWN',
    notes TEXT,
    source_type TEXT NOT NULL DEFAULT 'USER_REPORTED',
    model_version TEXT NOT NULL,
    UNIQUE(environment_key, effective_from, model_version)
);

CREATE TABLE IF NOT EXISTS investor_style_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_key TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    sample_count INTEGER NOT NULL,
    win_rate REAL,
    profit_factor REAL,
    median_holding_days REAL,
    average_holding_days REAL,
    long_pnl REAL,
    short_pnl REAL,
    drift_reason TEXT NOT NULL DEFAULT 'UNKNOWN',
    confidence REAL NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    evidence_json TEXT,
    model_version TEXT NOT NULL,
    UNIQUE(period_key, model_version)
);

CREATE TABLE IF NOT EXISTS environment_fit_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment_key TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    environment_fit_score REAL NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    factor_json TEXT NOT NULL,
    explanation TEXT,
    model_version TEXT NOT NULL,
    UNIQUE(environment_key, evaluated_at, model_version)
);

CREATE TABLE IF NOT EXISTS security_lifetime_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    realized_pnl REAL NOT NULL,
    profit_share REAL,
    trade_count INTEGER NOT NULL,
    win_rate REAL,
    profit_factor REAL,
    payoff_ratio REAL,
    largest_win REAL,
    largest_loss REAL,
    gross_profit REAL,
    gross_loss REAL,
    top1_loss_to_gross_profit REAL,
    loss_concentration_ratio REAL,
    long_pnl REAL,
    short_pnl REAL,
    classification TEXT NOT NULL DEFAULT 'RESEARCH',
    confidence REAL NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    evidence_json TEXT,
    model_version TEXT NOT NULL,
    UNIQUE(security_code, evaluated_at, model_version)
);

CREATE TABLE IF NOT EXISTS theme_lifetime_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_key TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    realized_pnl REAL NOT NULL,
    profit_share REAL,
    trade_count INTEGER NOT NULL,
    confidence REAL NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    evidence_json TEXT,
    model_version TEXT NOT NULL,
    UNIQUE(theme_key, evaluated_at, model_version)
);

CREATE TABLE IF NOT EXISTS risk_pattern_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT,
    evaluated_at TEXT NOT NULL,
    pattern_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO','WATCH','WARNING','CRITICAL')),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence_json TEXT NOT NULL,
    explanation TEXT NOT NULL,
    model_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_dna_fit_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    security_code TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    market_score REAL,
    dna_fit_score REAL,
    environment_fit_score REAL,
    capital_fit_score REAL,
    execution_difficulty REAL,
    final_personal_fit REAL,
    confidence REAL NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    factor_json TEXT NOT NULL,
    model_version TEXT NOT NULL,
    UNIQUE(trade_date, security_code, evaluated_at, model_version)
);

CREATE INDEX IF NOT EXISTS idx_environment_profiles_period
    ON investor_environment_profiles(effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_style_periods_period
    ON investor_style_periods(effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_lifetime_contrib_pnl
    ON security_lifetime_contributions(realized_pnl DESC);
CREATE INDEX IF NOT EXISTS idx_risk_patterns_security_time
    ON risk_pattern_assessments(security_code, evaluated_at);
CREATE INDEX IF NOT EXISTS idx_daily_dna_fit_date
    ON daily_dna_fit_assessments(trade_date, final_personal_fit DESC);
