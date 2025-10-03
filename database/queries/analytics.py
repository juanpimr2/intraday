"""
Queries de análisis y reportes
"""

import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from database.connection import DatabaseConnection


class AnalyticsQueries:
    """Queries de análisis y reportes"""
    
    def __init__(self):
        self.db = DatabaseConnection()
    
    def get_session_summary(self, session_id: Optional[int] = None, limit: int = 10) -> pd.DataFrame:
        """Obtiene resumen de sesiones"""
        query = "SELECT * FROM v_session_summary"
        params = []
        
        if session_id:
            query += " WHERE session_id = %s"
            params.append(session_id)
        
        query += f" LIMIT {limit}"
        
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)
    
    def get_trade_analysis(self, session_id: Optional[int] = None, 
                          epic: Optional[str] = None,
                          limit: int = 100) -> pd.DataFrame:
        """Análisis detallado de trades"""
        query = "SELECT * FROM v_trade_analysis WHERE 1=1"
        params = []
        
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        
        if epic:
            query += " AND epic = %s"
            params.append(epic)
        
        query += f" ORDER BY entry_time DESC LIMIT {limit}"
        
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)
    
    def get_epic_performance(self, session_id: Optional[int] = None) -> pd.DataFrame:
        """Performance por activo"""
        if session_id:
            query = """
                SELECT 
                    t.epic,
                    COUNT(*) AS total_trades,
                    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) AS losses,
                    ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::decimal / COUNT(*) * 100)::numeric, 2) AS win_rate,
                    SUM(t.pnl) AS total_pnl,
                    AVG(t.pnl) AS avg_pnl,
                    MAX(t.pnl) AS best_trade,
                    MIN(t.pnl) AS worst_trade
                FROM trades t
                WHERE t.status = 'CLOSED' AND t.session_id = %s
                GROUP BY t.epic
                ORDER BY total_pnl DESC
            """
            params = [session_id]
        else:
            query = "SELECT * FROM v_epic_performance"
            params = []
        
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)
    
    def get_daily_performance(self, session_id: Optional[int] = None,
                             days: int = 30) -> pd.DataFrame:
        """Performance diaria"""
        query = "SELECT * FROM v_daily_performance WHERE 1=1"
        params = []
        
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        
        query += f" ORDER BY trade_date DESC LIMIT {days}"
        
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)
    
    def compare_strategy_versions(self) -> pd.DataFrame:
        """Compara todas las versiones de estrategia"""
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT * FROM v_strategy_comparison")
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)

    def compare_two_versions(self, version1: str, version2: str) -> Dict:
        """Compara dos versiones específicas"""
        query = """
            SELECT 
                sv.version_name,
                COUNT(DISTINCT s.session_id) AS sessions,
                SUM(s.total_trades) AS total_trades,
                AVG(CASE WHEN s.total_trades > 0 
                    THEN s.winning_trades::decimal / s.total_trades * 100 
                    ELSE 0 END) AS avg_win_rate,
                SUM(s.total_pnl) AS total_pnl,
                AVG(s.max_drawdown) AS avg_drawdown,
                AVG(t.duration_minutes) AS avg_trade_duration,
                AVG(t.pnl) AS avg_pnl_per_trade,
                SUM(CASE WHEN t.exit_reason = 'TAKE_PROFIT' THEN 1 ELSE 0 END) AS tp_hits,
                SUM(CASE WHEN t.exit_reason = 'STOP_LOSS' THEN 1 ELSE 0 END) AS sl_hits
            FROM strategy_versions sv
            LEFT JOIN trading_sessions s ON sv.version_id = s.strategy_version_id
            LEFT JOIN trades t ON s.session_id = t.session_id AND t.status = 'CLOSED'
            WHERE sv.version_name IN (%s, %s)
            GROUP BY sv.version_name
            ORDER BY sv.version_name
        """
        
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute(query, (version1, version2))
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            df = pd.DataFrame(data, columns=columns)
            
            if len(df) < 2:
                return {'error': 'Una o ambas versiones no encontradas'}
            
            v1_data = df.iloc[0].to_dict()
            v2_data = df.iloc[1].to_dict()
            
            comparison = {
                'version1': v1_data,
                'version2': v2_data,
                'differences': {
                    'win_rate_diff': float(v2_data['avg_win_rate'] - v1_data['avg_win_rate']),
                    'pnl_diff': float(v2_data['total_pnl'] - v1_data['total_pnl']),
                    'drawdown_diff': float(v2_data['avg_drawdown'] - v1_data['avg_drawdown']),
                    'trades_diff': int(v2_data['total_trades'] - v1_data['total_trades'])
                },
                'winner': None
            }
            
            score_v1 = 0
            score_v2 = 0
            
            if v2_data['avg_win_rate'] > v1_data['avg_win_rate']:
                score_v2 += 1
            else:
                score_v1 += 1
            
            if v2_data['total_pnl'] > v1_data['total_pnl']:
                score_v2 += 1
            else:
                score_v1 += 1
            
            if v2_data['avg_drawdown'] < v1_data['avg_drawdown']:
                score_v2 += 1
            else:
                score_v1 += 1
            
            comparison['winner'] = version2 if score_v2 > score_v1 else version1
            comparison['score'] = {'v1': score_v1, 'v2': score_v2}
            
            return comparison
    
    def get_signal_effectiveness(self, epic: Optional[str] = None) -> pd.DataFrame:
        """Análisis de efectividad de señales"""
        query = "SELECT * FROM v_signal_effectiveness"
        params = []
        
        if epic:
            query += " WHERE epic = %s"
            params.append(epic)
        
        query += " ORDER BY win_rate_of_executed DESC NULLS LAST"
        
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)
    
    def get_exit_reason_analysis(self, session_id: Optional[int] = None) -> pd.DataFrame:
        """Análisis por razón de salida"""
        if session_id:
            query = """
                SELECT 
                    t.exit_reason,
                    COUNT(*) AS total_exits,
                    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS profitable,
                    SUM(t.pnl) AS total_pnl,
                    AVG(t.pnl) AS avg_pnl
                FROM trades t
                WHERE t.status = 'CLOSED' 
                    AND t.exit_reason IS NOT NULL
                    AND t.session_id = %s
                GROUP BY t.exit_reason
                ORDER BY total_exits DESC
            """
            params = [session_id]
        else:
            query = "SELECT * FROM v_exit_reason_analysis"
            params = []
        
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)
    
    def get_atr_effectiveness(self, session_id: Optional[int] = None) -> pd.DataFrame:
        """Análisis de efectividad por ATR"""
        if session_id:
            query = """
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
                    SUM(t.pnl) AS total_pnl
                FROM trades t
                WHERE t.status = 'CLOSED' 
                    AND t.atr_at_entry IS NOT NULL
                    AND t.session_id = %s
                GROUP BY atr_range
            """
            params = [session_id]
        else:
            query = "SELECT * FROM v_atr_effectiveness"
            params = []
        
        with self.db.get_cursor(commit=False) as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
            return pd.DataFrame(data, columns=columns)
    
    def export_full_report(self, session_id: int, format: str = 'excel') -> str:
        """Genera reporte completo de una sesión"""
        from datetime import datetime
        import os
        
        export_dir = 'exports'
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f'session_{session_id}_{timestamp}'
        
        if format == 'excel':
            filepath = os.path.join(export_dir, f'{base_filename}.xlsx')
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                self.get_session_summary(session_id).to_excel(writer, sheet_name='Summary', index=False)
                self.get_trade_analysis(session_id).to_excel(writer, sheet_name='Trades', index=False)
                self.get_epic_performance(session_id).to_excel(writer, sheet_name='By Epic', index=False)
                self.get_daily_performance(session_id).to_excel(writer, sheet_name='Daily', index=False)
                self.get_exit_reason_analysis(session_id).to_excel(writer, sheet_name='Exit Reasons', index=False)
                self.get_atr_effectiveness(session_id).to_excel(writer, sheet_name='ATR Analysis', index=False)
            
            return filepath
        
        elif format == 'json':
            filepath = os.path.join(export_dir, f'{base_filename}.json')
            
            report = {
                'session_id': session_id,
                'exported_at': datetime.now().isoformat(),
                'summary': self.get_session_summary(session_id).to_dict(orient='records'),
                'trades': self.get_trade_analysis(session_id).to_dict(orient='records'),
                'epic_performance': self.get_epic_performance(session_id).to_dict(orient='records'),
                'daily_performance': self.get_daily_performance(session_id).to_dict(orient='records')
            }
            
            import json
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            
            return filepath
        
        else:
            raise ValueError(f"Formato no soportado: {format}")
