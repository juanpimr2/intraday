-- v001_initial_schema.sql
-- Schema inicial del bot de trading

CREATE TABLE IF NOT EXISTS strategy_versions (
    version_id SERIAL PRIMARY KEY,
    version_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    config_snapshot JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE,
    changes TEXT[],
    expected_improvements TEXT,
    backtest_win_rate DECIMAL(6, 4),
    backtest_profit_factor DECIMAL(8, 4),
    backtest_total_trades INTEGER,
    demo_win_rate DECIMAL(6, 4),
    demo_days_tested INTEGER
);

CREATE INDEX idx_strategy_versions_active ON strategy_versions(is_active, created_at DESC);

CREATE TABLE IF NOT EXISTS trading_sessions (
    session_id SERIAL PRIMARY KEY,
    strategy_version_id INTEGER REFERENCES strategy_versions(version_id),
    start_time TIMESTAMP NOT NULL DEFAULT NOW(),
    end_time TIMESTAMP,
    initial_balance DECIMAL(12, 2) NOT NULL,
    final_balance DECIMAL(12, 2),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(12, 2) DEFAULT 0,
    max_drawdown DECIMAL(8, 4),
    status VARCHAR(20) DEFAULT 'RUNNING',
    config_snapshot JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_start_time ON trading_sessions(start_time DESC);
CREATE INDEX idx_sessions_strategy ON trading_sessions(strategy_version_id, start_time DESC);

CREATE TABLE IF NOT EXISTS account_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    balance DECIMAL(12, 2) NOT NULL,
    available DECIMAL(12, 2) NOT NULL,
    margin_used DECIMAL(12, 2) NOT NULL,
    margin_percent DECIMAL(8, 4) NOT NULL,
    open_positions_count INTEGER DEFAULT 0,
    equity DECIMAL(12, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_snapshots_session ON account_snapshots(session_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS market_signals (
    signal_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    epic VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    signal VARCHAR(10) NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL,
    current_price DECIMAL(12, 6) NOT NULL,
    rsi DECIMAL(6, 2),
    macd DECIMAL(12, 6),
    macd_signal DECIMAL(12, 6),
    macd_hist DECIMAL(12, 6),
    sma_short DECIMAL(12, 6),
    sma_long DECIMAL(12, 6),
    momentum DECIMAL(8, 4),
    atr_percent DECIMAL(8, 4),
    adx DECIMAL(6, 2),
    plus_di DECIMAL(6, 2),
    minus_di DECIMAL(6, 2),
    slow_trend VARCHAR(20),
    reasons TEXT[],
    indicators_json JSONB,
    executed BOOLEAN DEFAULT FALSE,
    trade_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_signals_session_epic ON market_signals(session_id, epic, timestamp DESC);
CREATE INDEX idx_signals_executed ON market_signals(executed, timestamp DESC);
CREATE INDEX idx_signals_confidence ON market_signals(confidence DESC);

CREATE TABLE IF NOT EXISTS trades (
    trade_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    signal_id INTEGER REFERENCES market_signals(signal_id),
    deal_reference VARCHAR(100),
    epic VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    entry_price DECIMAL(12, 6) NOT NULL,
    position_size DECIMAL(12, 6) NOT NULL,
    stop_loss DECIMAL(12, 6) NOT NULL,
    take_profit DECIMAL(12, 6) NOT NULL,
    margin_used DECIMAL(12, 2) NOT NULL,
    confidence DECIMAL(5, 4),
    sl_tp_mode VARCHAR(20),
    atr_at_entry DECIMAL(8, 4),
    exit_time TIMESTAMP,
    exit_price DECIMAL(12, 6),
    exit_reason VARCHAR(50),
    pnl DECIMAL(12, 2),
    pnl_percent DECIMAL(8, 4),
    duration_minutes INTEGER,
    status VARCHAR(20) DEFAULT 'OPEN',
    entry_reasons TEXT[],
    entry_indicators JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trades_session ON trades(session_id, entry_time DESC);
CREATE INDEX idx_trades_epic ON trades(epic, entry_time DESC);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_pnl ON trades(pnl DESC NULLS LAST);
CREATE INDEX idx_trades_exit_reason ON trades(exit_reason);

CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    period_type VARCHAR(20) NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(6, 4),
    total_pnl DECIMAL(12, 2) DEFAULT 0,
    avg_win DECIMAL(12, 2),
    avg_loss DECIMAL(12, 2),
    largest_win DECIMAL(12, 2),
    largest_loss DECIMAL(12, 2),
    profit_factor DECIMAL(8, 4),
    max_drawdown DECIMAL(8, 4),
    avg_trade_duration_minutes INTEGER,
    sharpe_ratio DECIMAL(8, 4),
    metrics_by_epic JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_metrics_session_period ON performance_metrics(session_id, period_type, period_start DESC);

CREATE TABLE IF NOT EXISTS backtest_results (
    backtest_id SERIAL PRIMARY KEY,
    strategy_version_id INTEGER REFERENCES strategy_versions(version_id),
    backtest_name VARCHAR(200) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(12, 2) NOT NULL,
    final_capital DECIMAL(12, 2) NOT NULL,
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    win_rate DECIMAL(6, 4),
    total_return DECIMAL(12, 2),
    total_return_percent DECIMAL(8, 4),
    max_drawdown DECIMAL(8, 4),
    profit_factor DECIMAL(8, 4),
    sharpe_ratio DECIMAL(8, 4),
    avg_trade_duration_minutes INTEGER,
    config_used JSONB,
    trades_detail JSONB,
    equity_curve JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_backtest_version ON backtest_results(strategy_version_id, created_at DESC);
CREATE INDEX idx_backtest_date ON backtest_results(start_date DESC, end_date DESC);

CREATE TABLE IF NOT EXISTS system_logs (
    log_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    level VARCHAR(20) NOT NULL,
    module VARCHAR(100),
    message TEXT NOT NULL,
    exception_trace TEXT,
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_logs_session_level ON system_logs(session_id, level, timestamp DESC);
CREATE INDEX idx_logs_timestamp ON system_logs(timestamp DESC);

COMMENT ON TABLE strategy_versions IS 'Versiones de la estrategia para comparar mejoras';
COMMENT ON TABLE trading_sessions IS 'Sesiones de trading del bot';
COMMENT ON TABLE trades IS 'Operaciones ejecutadas con entrada y salida';
