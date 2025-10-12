"""
Queries de analytics para reporting y exports
VERSIÓN COMPLETA con todos los métodos necesarios
"""

import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List, Optional
from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class AnalyticsQueries:
    """Queries de analytics y reporting"""
    
    def __init__(self):
        self.db = DatabaseConnection()
    
    # ============================================
    # SESIONES
    # ============================================
    
    def get_sessions_summary(self, limit: int = 20) -> List[Dict]:
        """Obtiene resumen de sesiones"""
        query = """
            SELECT * FROM v_session_summary
            ORDER BY start_time DESC
            LIMIT %s
        """
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (limit,))
            return cursor.fetchall()
    
    def get_session_info(self, session_id: int) -> Dict:
        """Obtiene información de una sesión específica"""
        query = """
            SELECT * FROM v_session_summary
            WHERE session_id = %s
        """
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (session_id,))
            result = cursor.fetchone()
            return result if result else {}
    
    # ============================================
    # TRADES
    # ============================================
    
    def get_trades_by_session(self, session_id: int) -> List[Dict]:
        """Obtiene todos los trades de una sesión"""
        query = """
            SELECT 
                trade_id,
                epic,
                direction,
                entry_price,
                exit_price,
                position_size AS size,  -- alias de compatibilidad
                pnl,
                pnl_percent,
                entry_time,
                exit_time,
                exit_reason,
                confidence
            FROM trades
            WHERE session_id = %s
            ORDER BY entry_time DESC
        """
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (session_id,))
            return cursor.fetchall()
    
    def get_recent_trades(self, limit: int = 100) -> List[Dict]:
        """Obtiene los últimos N trades"""
        query = """
            SELECT 
                trade_id,
                session_id,
                epic,
                direction,
                entry_price,
                exit_price,
                position_size AS size,  -- alias de compatibilidad
                pnl,
                pnl_percent,
                entry_time,
                exit_time,
                exit_reason,
                confidence
            FROM trades
            ORDER BY entry_time DESC
            LIMIT %s
        """
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (limit,))
            return cursor.fetchall()
    
    def get_trade_analysis(self, session_id: Optional[int] = None) -> Dict:
        """Obtiene análisis detallado de trades"""
        if session_id:
            query = "SELECT * FROM v_trade_analysis WHERE session_id = %s"
            params = (session_id,)
        else:
            query = """
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                    AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
                    MAX(CASE WHEN pnl > 0 THEN pnl END) as max_win,
                    MIN(CASE WHEN pnl < 0 THEN pnl END) as max_loss,
                    SUM(pnl) as total_pnl
                FROM trades
            """
            params = None
        
        with self.db.get_cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = cursor.fetchone()
            return result if result else {}
    
    def get_global_stats(self) -> Dict:
        """Estadísticas globales de todos los trades"""
        return self.get_trade_analysis(session_id=None)
    
    # ============================================
    # SEÑALES
    # ============================================
    
    def get_signals_by_session(self, session_id: int) -> List[Dict]:
        """Obtiene señales de una sesión"""
        query = """
            SELECT 
                signal_id,
                epic,
                signal_type,
                confidence,
                current_price,
                indicators,
                reasons,
                executed,
                created_at
            FROM market_signals
            WHERE session_id = %s
            ORDER BY created_at DESC
        """
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (session_id,))
            return cursor.fetchall()
    
    def get_recent_signals(self, limit: int = 50) -> List[Dict]:
        """Obtiene las señales más recientes"""
        query = """
            SELECT 
                signal_id,
                session_id,
                epic,
                signal_type,
                confidence,
                current_price,
                indicators,
                reasons,
                executed,
                created_at
            FROM market_signals
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (limit,))
            return cursor.fetchall()
    
    # ============================================
    # EXPORTS
    # ============================================
    
    def export_trades(self, session_id: int, format: str = 'csv') -> str:
        """
        Exporta trades de una sesión a CSV o Excel
        
        Args:
            session_id: ID de la sesión
            format: 'csv' o 'excel'
            
        Returns:
            str: Path del archivo generado
        """
        trades = self.get_trades_by_session(session_id)
        
        if not trades:
            logger.warning(f"No hay trades para exportar en sesión {session_id}")
            return None
        
        # Convertir a DataFrame
        df = pd.DataFrame(trades)
        
        # Formatear fechas
        if 'entry_time' in df.columns:
            df['entry_time'] = pd.to_datetime(df['entry_time'])
        if 'exit_time' in df.columns:
            df['exit_time'] = pd.to_datetime(df['exit_time'])
        
        # Generar filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == 'csv':
            filename = f'exports/trades_session_{session_id}_{timestamp}.csv'
            df.to_csv(filename, index=False, encoding='utf-8')
        elif format == 'excel':
            filename = f'exports/trades_session_{session_id}_{timestamp}.xlsx'
            df.to_excel(filename, index=False, sheet_name='Trades')
        else:
            raise ValueError(f"Formato no válido: {format}")
        
        logger.info(f"Trades exportados a {filename}")
        return filename
    
    def export_all_trades(self, format: str = 'csv') -> str:
        """Exporta todos los trades"""
        trades = self.get_recent_trades(limit=10000)
        
        if not trades:
            logger.warning("No hay trades para exportar")
            return None
        
        df = pd.DataFrame(trades)
        
        # Formatear fechas
        if 'entry_time' in df.columns:
            df['entry_time'] = pd.to_datetime(df['entry_time'])
        if 'exit_time' in df.columns:
            df['exit_time'] = pd.to_datetime(df['exit_time'])
        
        # Generar filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == 'csv':
            filename = f'exports/all_trades_{timestamp}.csv'
            df.to_csv(filename, index=False, encoding='utf-8')
        elif format == 'excel':
            filename = f'exports/all_trades_{timestamp}.xlsx'
            df.to_excel(filename, index=False, sheet_name='All Trades')
        else:
            raise ValueError(f"Formato no válido: {format}")
        
        logger.info(f"Todos los trades exportados a {filename}")
        return filename
    
    def export_full_report(self, session_id: int, format: str = 'excel') -> str:
        """
        Genera un reporte completo con múltiples hojas
        
        Args:
            session_id: ID de la sesión
            format: Solo 'excel' soportado
            
        Returns:
            str: Path del archivo generado
        """
        if format != 'excel':
            raise ValueError("Solo formato Excel soportado para reportes completos")
        
        # Obtener datos
        session_info = self.get_session_info(session_id)
        trades = self.get_trades_by_session(session_id)
        stats = self.get_trade_analysis(session_id)
        signals = self.get_signals_by_session(session_id)
        
        if not session_info:
            logger.warning(f"Sesión {session_id} no encontrada")
            return None
        
        # Crear filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'exports/report_session_{session_id}_{timestamp}.xlsx'
        
        # Crear Excel writer
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Hoja 1: Resumen de la sesión
            session_df = pd.DataFrame([session_info])
            session_df.to_excel(writer, sheet_name='Resumen', index=False)
            
            # Hoja 2: Trades
            if trades:
                trades_df = pd.DataFrame(trades)
                if 'entry_time' in trades_df.columns:
                    trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
                if 'exit_time' in trades_df.columns:
                    trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
                trades_df.to_excel(writer, sheet_name='Trades', index=False)
            
            # Hoja 3: Estadísticas
            if stats:
                stats_df = pd.DataFrame([stats])
                stats_df.to_excel(writer, sheet_name='Estadísticas', index=False)
            
            # Hoja 4: Señales
            if signals:
                signals_df = pd.DataFrame(signals)
                if 'created_at' in signals_df.columns:
                    signals_df['created_at'] = pd.to_datetime(signals_df['created_at'])
                signals_df.to_excel(writer, sheet_name='Señales', index=False)
        
        logger.info(f"Reporte completo generado: {filename}")
        return filename
    
    # ============================================
    # ANÁLISIS ESPECÍFICOS
    # ============================================
    
    def get_win_rate_by_asset(self, session_id: Optional[int] = None) -> List[Dict]:
        """Win rate por activo"""
        if session_id:
            query = "SELECT * FROM v_win_rate_by_asset WHERE session_id = %s"
            params = (session_id,)
        else:
            query = """
                SELECT 
                    epic,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                    ROUND(100.0 * SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
                    SUM(pnl) as total_pnl
                FROM trades
                GROUP BY epic
                ORDER BY total_trades DESC
            """
            params = None
        
        with self.db.get_cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
    
    def get_daily_pnl(self, session_id: Optional[int] = None) -> List[Dict]:
        """P&L por día"""
        if session_id:
            query = """
                SELECT 
                    DATE(exit_time) as trade_date,
                    COUNT(*) as trades,
                    SUM(pnl) as daily_pnl,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses
                FROM trades
                WHERE session_id = %s AND exit_time IS NOT NULL
                GROUP BY DATE(exit_time)
                ORDER BY trade_date DESC
            """
            params = (session_id,)
        else:
            query = """
                SELECT 
                    DATE(exit_time) as trade_date,
                    COUNT(*) as trades,
                    SUM(pnl) as daily_pnl,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses
                FROM trades
                WHERE exit_time IS NOT NULL
                GROUP BY DATE(exit_time)
                ORDER BY trade_date DESC
            """
            params = None
        
        with self.db.get_cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
    
    def get_signal_effectiveness(self, session_id: Optional[int] = None) -> Dict:
        """Efectividad de las señales (% ejecutadas que fueron ganadoras)"""
        if session_id:
            query = """
                SELECT 
                    COUNT(DISTINCT ms.signal_id) as total_signals,
                    SUM(CASE WHEN ms.executed THEN 1 ELSE 0 END) as executed_signals,
                    COUNT(t.trade_id) as trades_from_signals,
                    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    AVG(ms.confidence) as avg_confidence
                FROM market_signals ms
                LEFT JOIN trades t ON ms.epic = t.epic 
                    AND ms.created_at BETWEEN t.entry_time - INTERVAL '5 minutes' 
                    AND t.entry_time + INTERVAL '5 minutes'
                WHERE ms.session_id = %s
            """
            params = (session_id,)
        else:
            query = """
                SELECT 
                    COUNT(DISTINCT ms.signal_id) as total_signals,
                    SUM(CASE WHEN ms.executed THEN 1 ELSE 0 END) as executed_signals,
                    COUNT(t.trade_id) as trades_from_signals,
                    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    AVG(ms.confidence) as avg_confidence
                FROM market_signals ms
                LEFT JOIN trades t ON ms.epic = t.epic 
                    AND ms.created_at BETWEEN t.entry_time - INTERVAL '5 minutes' 
                    AND t.entry_time + INTERVAL '5 minutes'
            """
            params = None
        
        with self.db.get_cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = cursor.fetchone()
            return result if result else {}