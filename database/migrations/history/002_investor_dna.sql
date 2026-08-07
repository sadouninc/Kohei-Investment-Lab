PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS investor_dna_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluated_at TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    win_rate REAL,
    profit_factor REAL,
    median_holding_days REAL,
    average_holding_days REAL,
    model_version TEXT NOT NULL,
    source_reference TEXT,
    UNIQUE(evaluated_at, model_version)
);

CREATE TABLE IF NOT EXISTS security_behavior_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    win_rate REAL,
    profit_factor REAL,
    payoff_ratio REAL,
    median_holding_days REAL,
    average_holding_days REAL,
    average_return_rate REAL,
    median_post_exit_return_1d REAL,
    median_post_exit_return_3d REAL,
    median_post_exit_return_5d REAL,
    median_post_exit_return_10d REAL,
    median_post_exit_return_20d REAL,
    median_days_to_post_exit_peak REAL,
    model_version TEXT NOT NULL,
    UNIQUE(security_code, evaluated_at, model_version)
);

CREATE TABLE IF NOT EXISTS compatibility_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    compatibility_score REAL NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    primary_mismatch_code TEXT NOT NULL,
    recommended_portfolio_role TEXT,
    recommended_horizon TEXT,
    explanation TEXT,
    model_version TEXT NOT NULL,
    UNIQUE(security_code, evaluated_at, model_version)
);

CREATE TABLE IF NOT EXISTS compatibility_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL,
    factor_key TEXT NOT NULL,
    factor_score REAL,
    evidence_value REAL,
    evidence_text TEXT,
    cause_code TEXT,
    FOREIGN KEY (assessment_id) REFERENCES compatibility_assessments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS strategy_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_code TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    experiment_type TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    rule_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PLANNED' CHECK (status IN ('PLANNED','ACTIVE','COMPLETED','ABANDONED')),
    result_summary TEXT,
    baseline_assessment_id INTEGER,
    followup_assessment_id INTEGER,
    FOREIGN KEY (baseline_assessment_id) REFERENCES compatibility_assessments(id),
    FOREIGN KEY (followup_assessment_id) REFERENCES compatibility_assessments(id)
);

CREATE INDEX IF NOT EXISTS idx_dna_security_time
    ON compatibility_assessments(security_code, evaluated_at);
CREATE INDEX IF NOT EXISTS idx_dna_factors_assessment
    ON compatibility_factors(assessment_id, factor_key);
CREATE INDEX IF NOT EXISTS idx_dna_experiments_security
    ON strategy_experiments(security_code, created_at);
