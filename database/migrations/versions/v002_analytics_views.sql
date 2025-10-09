CREATE OR REPLACE VIEW active_trades AS
SELECT 
    t.trade_id,
    t.deal_reference,
    t.epic,
    t.direction,
    t.entry_price,
    t.position_size,
    t.stop_loss,
    t.take_profit,
    t.margin_used,
    t.entry_time,
    EXTRACT(EPOCH FROM (NOW() - t.entry_time))/60 as minutes_open
FROM trades t
WHERE t.status = 'OPEN'
ORDER BY t.entry_time DESC;

CREATE OR REPLACE VIEW daily_summary AS
SELECT 
    DATE(entry_time) as trading_date,
    COUNT(*) as total_trades,
    COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
    COUNT(CASE WHEN pnl < 0 THEN 1 END) as losing_trades,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl,
    MAX(pnl) as best_trade,
    MIN(pnl) as worst_trade,
    COUNT(DISTINCT epic) as assets_traded
FROM trades
WHERE status = 'CLOSED'
GROUP BY DATE(entry_time)
ORDER BY trading_date DESC;

CREATE OR REPLACE VIEW performance_by_asset AS
SELECT 
    epic,
    COUNT(*) as total_trades,
    COUNT(CASE WHEN pnl > 0 THEN 1 END) as wins,
    COUNT(CASE WHEN pnl < 0 THEN 1 END) as losses,
    ROUND(COUNT(CASE WHEN pnl > 0 THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) as win_rate,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl
FROM trades
WHERE status = 'CLOSED'
GROUP BY epic
ORDER BY total_pnl DESC;

CREATE OR REPLACE VIEW latest_account_state AS
SELECT 
    s.*,
    (s.balance - ts.initial_balance) as session_pnl,
    ROUND((s.balance - ts.initial_balance) / ts.initial_balance * 100, 2) as session_pnl_percent
FROM account_snapshots s
JOIN trading_sessions ts ON s.session_id = ts.session_id
WHERE s.snapshot_id = (
    SELECT MAX(snapshot_id) 
    FROM account_snapshots
);
