-- v002_analytics_views.sql
-- Vistas SQL para análisis y comparativas

-- ============================================
-- VISTA: v_session_summary
-- ============================================
CREATE OR REPLACE VIEW v_session_summary AS
SELECT 
    s.session_id,
    s.start_time,
    s.end_time,
    EXTRACT(EPOCH FROM (s.end_time - s.start_time))/3600 AS duration_hours,
    sv.version_name AS strategy_version,
    s.initial_balance,
    s.final_balance,
    s.final_balance - s.initial_balance AS total_profit,
    ROUND(((s.final_balance - s.initial_balance) / s.initial_balance * 100)::numeric, 2) AS roi_percent,
    s.total_trades,
    s.winning_trades,
    s.losing_trades,
    CASE 
        WHEN s.total_trades > 0 THEN ROUND((s.winning_trades::decimal / s.total_trades * 100)::numeric, 2)
        ELSE 0 
    END AS win_rate_percent,
    s.total_pnl,
    s.max_drawdown,
    s.status
FROM trading_sessions s
LEFT JOIN strategy_versions sv ON s.strategy_version_id = sv.version_id
ORDER BY s.start_time DESC;

-- ============================================
-- VISTA: v_trade_analysis
-- ============================================
CREATE OR REPLACE VIEW v_trade_analysis AS
SELECT 
    t.trade_id,
    t.session_id,
    t.epic,
    t.direction,
    t.entry_time,
    t.exit_time,
    t.duration_minutes,
    t.entry_price,
    t.exit_price,
    t.position_size,
    t.stop_loss,
    t.take_profit,
    ROUND(ABS(t.entry_price - t.stop_loss) / t.entry_price * 100, 2) AS sl_distance_percent,
    ROUND(ABS(t.take_profit - t.entry_price) / t.entry_price * 100, 2) AS tp_distance_percent,
    CASE 
        WHEN t.direction = 'BUY' THEN 
            ROUND((ABS(t.take_profit - t.entry_price) / ABS(t.entry_price - t.stop_loss))::numeric, 2)
        ELSE 
            ROUND((ABS(t.entry_price - t.take_profit) / ABS(t.stop_loss - t.entry_price))::numeric, 2)
    END AS risk_reward_ratio,
    t.pnl,
    t.pnl_percent,
    CASE 
        WHEN t.pnl > 0 THEN 'WIN'
        WHEN t.pnl < 0 THEN 'LOSS'
        ELSE 'BREAK_EVEN'
    END AS result,
    t.exit_reason,
    t.sl_tp_mode,
    t.atr_at_entry,
    t.confidence,
    t.status
FROM trades t
WHERE t.status = 'CLOSED'
ORDER BY t.entry_time DESC;

-- ============================================
-- VISTA: v_epic_performance
-- ============================================
CREATE OR REPLACE VIEW v_epic_performance AS
SELECT 
    t.epic,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) AS losses,
    ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::decimal / COUNT(*) * 100)::numeric, 2) AS win_rate,
    SUM(t.pnl) AS total_pnl,
    AVG(t.pnl) AS avg_pnl,
    MAX(t.pnl) AS best_trade,
    MIN(t.pnl) AS worst_trade,
    AVG(t.duration_minutes) AS avg_duration_minutes,
    CASE 
        WHEN SUM(CASE WHEN t.pnl < 0 THEN ABS(t.pnl) ELSE 0 END) > 0 THEN
            ROUND((SUM(CASE WHEN t.pnl > 0 THEN t.pnl ELSE 0 END) / 
                   SUM(CASE WHEN t.pnl < 0 THEN ABS(t.pnl) ELSE 0 END))::numeric, 2)
        ELSE NULL
    END AS profit_factor
FROM trades t
WHERE t.status = 'CLOSED'
GROUP BY t.epic
ORDER BY total_pnl DESC;

-- ============================================
-- VISTA: v_strategy_comparison
-- ============================================
CREATE OR REPLACE VIEW v_strategy_comparison AS
SELECT 
    sv.version_name,
    sv.description,
    sv.created_at AS version_created,
    sv.backtest_win_rate * 100 AS backtest_win_rate_pct,
    sv.backtest_profit_factor,
    sv.backtest_total_trades,
    COUNT(DISTINCT s.session_id) AS total_sessions,
    SUM(s.total_trades) AS total_trades_live,
    ROUND(AVG(
        CASE 
            WHEN s.total_trades > 0 THEN s.winning_trades::decimal / s.total_trades * 100
            ELSE 0 
        END
    )::numeric, 2) AS avg_win_rate_live,
    SUM(s.total_pnl) AS total_pnl_live,
    AVG(s.max_drawdown) * 100 AS avg_max_drawdown_pct,
    ROUND((
        AVG(CASE WHEN s.total_trades > 0 THEN s.winning_trades::decimal / s.total_trades * 100 ELSE 0 END) - 
        (sv.backtest_win_rate * 100)
    )::numeric, 2) AS win_rate_diff_backtest_vs_live
FROM strategy_versions sv
LEFT JOIN trading_sessions s ON sv.version_id = s.strategy_version_id
GROUP BY sv.version_id, sv.version_name, sv.description, sv.created_at,
         sv.backtest_win_rate, sv.backtest_profit_factor, sv.backtest_total_trades
ORDER BY sv.created_at DESC;

-- ============================================
-- VISTA: v_daily_performance
-- ============================================
CREATE OR REPLACE VIEW v_daily_performance AS
SELECT 
    DATE(t.entry_time) AS trade_date,
    t.session_id,
    COUNT(*) AS trades,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) AS losses,
    ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::decimal / COUNT(*) * 100)::numeric, 2) AS win_rate,
    SUM(t.pnl) AS daily_pnl,
    AVG(t.pnl) AS avg_pnl_per_trade,
    MAX(t.pnl) AS best_trade,
    MIN(t.pnl) AS worst_trade
FROM trades t
WHERE t.status = 'CLOSED'
GROUP BY DATE(t.entry_time), t.session_id
ORDER BY DATE(t.entry_time) DESC;

-- ============================================
-- VISTA: v_signal_effectiveness
-- ============================================
CREATE OR REPLACE VIEW v_signal_effectiveness AS
SELECT 
    ms.epic,
    ms.signal,
    COUNT(*) AS total_signals,
    SUM(CASE WHEN ms.executed THEN 1 ELSE 0 END) AS executed_signals,
    ROUND((SUM(CASE WHEN ms.executed THEN 1 ELSE 0 END)::decimal / COUNT(*) * 100)::numeric, 2) 
        AS execution_rate,
    ROUND(AVG(ms.confidence)::numeric, 4) AS avg_confidence,
    ROUND(AVG(ms.rsi)::numeric, 2) AS avg_rsi,
    ROUND(AVG(ms.adx)::numeric, 2) AS avg_adx,
    ROUND(AVG(ms.atr_percent)::numeric, 2) AS avg_atr_percent,
    COUNT(t.trade_id) AS trades_closed,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS profitable_trades,
    ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::decimal / 
           NULLIF(COUNT(t.trade_id), 0) * 100)::numeric, 2) AS win_rate_of_executed
FROM market_signals ms
LEFT JOIN trades t ON ms.trade_id = t.trade_id AND t.status = 'CLOSED'
WHERE ms.signal IN ('BUY', 'SELL')
GROUP BY ms.epic, ms.signal
ORDER BY win_rate_of_executed DESC NULLS LAST;

-- ============================================
-- VISTA: v_exit_reason_analysis
-- ============================================
CREATE OR REPLACE VIEW v_exit_reason_analysis AS
SELECT 
    t.exit_reason,
    COUNT(*) AS total_exits,
    ROUND((COUNT(*)::decimal / (SELECT COUNT(*) FROM trades WHERE status = 'CLOSED') * 100)::numeric, 2) 
        AS percentage,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS profitable,
    SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) AS unprofitable,
    SUM(t.pnl) AS total_pnl,
    AVG(t.pnl) AS avg_pnl,
    AVG(t.duration_minutes) AS avg_duration_minutes
FROM trades t
WHERE t.status = 'CLOSED' AND t.exit_reason IS NOT NULL
GROUP BY t.exit_reason
ORDER BY total_exits DESC;

-- ============================================
-- VISTA: v_atr_effectiveness
-- ============================================
CREATE OR REPLACE VIEW v_atr_effectiveness AS
SELECT 
    CASE 
        WHEN t.atr_at_entry < 0.5 THEN '< 0.5%'
        WHEN t.atr_at_entry >= 0.5 AND t.atr_at_entry < 1.0 THEN '0.5-1.0%'
        WHEN t.atr_at_entry >= 1.0 AND t.atr_at_entry < 2.0 THEN '1.0-2.0%'
        WHEN t.atr_at_entry >= 2.0 AND t.atr_at_entry < 3.0 THEN '2.0-3.0%'
        WHEN t.atr_at_entry >= 3.0 THEN '> 3.0%'
        ELSE 'Unknown'
    END AS atr_range,
    COUNT(*) AS trades,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS wins,
    ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::decimal / COUNT(*) * 100)::numeric, 2) AS win_rate,
    SUM(t.pnl) AS total_pnl,
    AVG(t.pnl) AS avg_pnl,
    AVG(t.duration_minutes) AS avg_duration
FROM trades t
WHERE t.status = 'CLOSED' AND t.atr_at_entry IS NOT NULL
GROUP BY atr_range
ORDER BY 
    CASE atr_range
        WHEN '< 0.5%' THEN 1
        WHEN '0.5-1.0%' THEN 2
        WHEN '1.0-2.0%' THEN 3
        WHEN '2.0-3.0%' THEN 4
        WHEN '> 3.0%' THEN 5
        ELSE 6
    END;

COMMENT ON VIEW v_session_summary IS 'Resumen ejecutivo de sesiones';
COMMENT ON VIEW v_trade_analysis IS 'Análisis detallado de trades';
COMMENT ON VIEW v_epic_performance IS 'Performance por activo';
COMMENT ON VIEW v_strategy_comparison IS 'Comparación entre versiones';
