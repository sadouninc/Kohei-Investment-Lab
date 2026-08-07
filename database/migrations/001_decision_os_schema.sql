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
    UNIQUE(security_code, timeframe, observed_at, source),
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

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('MARKET','THEME','SECURITY')),
    scope_id TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    direction TEXT,
    strength REAL,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    raw_reference TEXT,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('MARKET','THEME','SECURITY')),
    scope_id TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    state TEXT NOT NULL,
    trend_direction TEXT,
    trend_strength REAL,
    momentum REAL,
    acceleration REAL,
    volatility REAL,
    breadth REAL,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    total_market_value REAL,
    total_cost REAL,
    unrealized_pnl REAL,
    realized_pnl_ytd REAL,
    source TEXT,
    source_version TEXT
);

CREATE TABLE IF NOT EXISTS position_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_snapshot_id INTEGER NOT NULL,
    security_code TEXT NOT NULL,
    account_type TEXT,
    side TEXT NOT NULL CHECK (side IN ('LONG','SHORT')),
    quantity REAL NOT NULL,
    average_price REAL,
    market_price REAL,
    market_value REAL,
    unrealized_pnl REAL,
    portfolio_role TEXT CHECK (portfolio_role IS NULL OR portfolio_role IN ('CORE','TREND')),
    capital_bucket TEXT,
    FOREIGN KEY (portfolio_snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE CASCADE,
    FOREIGN KEY (security_code) REFERENCES decision_securities(security_code)
);

CREATE TABLE IF NOT EXISTS capital_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    cash_buying_power REAL,
    margin_buying_power REAL,
    cash_ratio REAL,
    margin_exposure REAL,
    margin_ratio REAL,
    total_exposure REAL,
    reserve_amount REAL,
    source TEXT,
    source_version TEXT
);

CREATE TABLE IF NOT EXISTS capital_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    capital_snapshot_id INTEGER,
    market_state_id INTEGER,
    posture TEXT NOT NULL CHECK (posture IN ('AGGRESSIVE','NEUTRAL','DEFENSIVE','CAPITAL_PRESERVATION')),
    target_cash_ratio_min REAL,
    target_cash_ratio_max REAL,
    target_reserve_amount REAL,
    core_target_ratio REAL,
    trend_target_ratio REAL,
    reason_json TEXT,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    FOREIGN KEY (capital_snapshot_id) REFERENCES capital_snapshots(id),
    FOREIGN KEY (market_state_id) REFERENCES market_states(id)
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    security_code TEXT NOT NULL,
    horizon TEXT NOT NULL CHECK (horizon IN ('ULTRA_SHORT','SHORT_SWING','MEDIUM_TERM','LONG_TERM')),
    universe_state TEXT,
    long_score REAL,
    today_score REAL,
    trend_score REAL,
    risk_score REAL,
    personal_fit REAL,
    capital_feasibility REAL,
    rotation_score REAL,
    rank INTEGER,
    status TEXT NOT NULL CHECK (status IN ('STRONG_BUY_CANDIDATE','BUY_CANDIDATE','WATCH','HOLD','REDUCE_CANDIDATE','EXIT_REVIEW')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    FOREIGN KEY (security_code) REFERENCES decision_securities(security_code)
);

CREATE TABLE IF NOT EXISTS candidate_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    factor_type TEXT NOT NULL,
    factor_key TEXT NOT NULL,
    value_numeric REAL,
    value_text TEXT,
    contribution REAL,
    polarity TEXT CHECK (polarity IS NULL OR polarity IN ('POSITIVE','NEGATIVE','NEUTRAL')),
    source_reference TEXT,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    security_code TEXT NOT NULL,
    candidate_detected_at TEXT,
    decision_at TEXT NOT NULL,
    ai_suggestion TEXT,
    human_decision TEXT NOT NULL CHECK (human_decision IN ('BUY','ADD','WATCH','HOLD','REDUCE','EXIT','NO_ACTION')),
    reason TEXT,
    decision_latency_sec INTEGER,
    price_at_detection REAL,
    price_at_decision REAL,
    capital_policy_id INTEGER,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id),
    FOREIGN KEY (security_code) REFERENCES decision_securities(security_code),
    FOREIGN KEY (capital_policy_id) REFERENCES capital_policies(id)
);

CREATE TABLE IF NOT EXISTS decision_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER NOT NULL,
    check_type TEXT NOT NULL,
    checked INTEGER NOT NULL CHECK (checked IN (0, 1)),
    result TEXT,
    checked_at TEXT,
    FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decision_trade_links (
    decision_id INTEGER NOT NULL,
    trade_id TEXT NOT NULL,
    PRIMARY KEY (decision_id, trade_id),
    FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_type TEXT NOT NULL CHECK (reference_type IN ('CANDIDATE','DECISION','TRADE','PREDICTION')),
    reference_id TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    horizon TEXT NOT NULL,
    start_price REAL,
    end_price REAL,
    return_pct REAL,
    excess_return_pct REAL,
    mfe_pct REAL,
    mae_pct REAL,
    benchmark TEXT,
    evaluation_version TEXT NOT NULL,
    UNIQUE(reference_type, reference_id, horizon, evaluation_version)
);

CREATE TABLE IF NOT EXISTS missed_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER,
    candidate_id INTEGER,
    security_code TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    missed_action TEXT NOT NULL CHECK (missed_action IN ('DID_NOT_BUY','DID_NOT_ADD','DID_NOT_SELL','DID_NOT_REDUCE')),
    reason_code TEXT,
    reason_text TEXT,
    reference_price REAL,
    capital_constraint INTEGER NOT NULL DEFAULT 0 CHECK (capital_constraint IN (0, 1)),
    availability_constraint INTEGER NOT NULL DEFAULT 0 CHECK (availability_constraint IN (0, 1)),
    FOREIGN KEY (decision_id) REFERENCES decisions(id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(id),
    FOREIGN KEY (security_code) REFERENCES decision_securities(security_code)
);

CREATE TABLE IF NOT EXISTS daily_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL UNIQUE,
    morning_routine_version TEXT,
    market_state_id INTEGER,
    portfolio_snapshot_id INTEGER,
    capital_snapshot_id INTEGER,
    morning_hypothesis TEXT,
    end_of_day_review TEXT,
    lessons TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (market_state_id) REFERENCES market_states(id),
    FOREIGN KEY (portfolio_snapshot_id) REFERENCES portfolio_snapshots(id),
    FOREIGN KEY (capital_snapshot_id) REFERENCES capital_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_universe_membership_time ON universe_membership(security_code, valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_market_observations_symbol_time ON market_observations(symbol, timeframe, observed_at);
CREATE INDEX IF NOT EXISTS idx_security_observations_code_time ON security_observations(security_code, timeframe, observed_at);
CREATE INDEX IF NOT EXISTS idx_signals_scope_time ON signals(scope_type, scope_id, timeframe, generated_at);
CREATE INDEX IF NOT EXISTS idx_market_states_scope_time ON market_states(scope_type, scope_id, timeframe, generated_at);
CREATE INDEX IF NOT EXISTS idx_positions_snapshot ON position_snapshots(portfolio_snapshot_id, security_code);
CREATE INDEX IF NOT EXISTS idx_candidates_time_rank ON candidates(generated_at, horizon, rank);
CREATE INDEX IF NOT EXISTS idx_candidates_security_time ON candidates(security_code, generated_at);
CREATE INDEX IF NOT EXISTS idx_decisions_security_time ON decisions(security_code, decision_at);
CREATE INDEX IF NOT EXISTS idx_outcomes_reference ON outcomes(reference_type, reference_id, horizon);
CREATE INDEX IF NOT EXISTS idx_missed_security_time ON missed_opportunities(security_code, recorded_at);
