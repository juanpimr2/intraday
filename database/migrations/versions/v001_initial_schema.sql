CREATE TABLE IF NOT EXISTS trading_sessions (
    session_id SERIAL PRIMARY KEY,
    start_time TIMESTAMP NOT NULL DEFAULT NOW(),
    end_time TIMESTAMP,
    initial_balance DECIMAL(12, 2) NOT NULL,
    final_balance DECIMAL(12, 2),
    total_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(12, 2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'RUNNING',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON trading_sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON trading_sessions(start_time DESC);

CREATE TABLE IF NOT EXISTS trades (
    trade_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id),
    deal_reference VARCHAR(100) UNIQUE,
    epic VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    entry_time TIMESTAMP NOT NULL,
    entry_price DECIMAL(12, 6) NOT NULL,
    position_size DECIMAL(12, 6) NOT NULL,
    stop_loss DECIMAL(12, 6),
    take_profit DECIMAL(12, 6),
    margin_used DECIMAL(12, 2),
    exit_time TIMESTAMP,
    exit_price DECIMAL(12, 6),
    exit_reason VARCHAR(50),
    pnl DECIMAL(12, 2),
    pnl_percent DECIMAL(8, 4),
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
    confidence DECIMAL(5, 4),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_epic ON trades(epic);
CREATE INDEX IF NOT EXISTS idx_trades_deal ON trades(deal_reference);
CREATE INDEX IF NOT EXISTS idx_trades_entry ON trades(entry_time DESC);

CREATE TABLE IF NOT EXISTS account_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    balance DECIMAL(12, 2) NOT NULL,
    available DECIMAL(12, 2) NOT NULL,
    margin_used DECIMAL(12, 2) NOT NULL,
    margin_percent DECIMAL(8, 4) NOT NULL,
    open_positions_count INTEGER DEFAULT 0,
    total_pnl DECIMAL(12, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_time ON account_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_session ON account_snapshots(session_id);
