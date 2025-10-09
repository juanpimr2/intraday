# database/database_manager.py
"""
Gestión de base de datos para el bot de trading - VERSIÓN SIMPLIFICADA
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestiona operaciones de base de datos - SIMPLIFICADO"""
    
    def __init__(self):
        """Inicializa el manager de base de datos"""
        self.db = DatabaseConnection()
        self.session_id = None
        logger.info("✅ DatabaseManager inicializado")
    
    def start_session(self, initial_balance: float) -> Optional[int]:
        """Inicia una nueva sesión de trading"""
        try:
            with self.db.get_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO trading_sessions 
                    (start_time, initial_balance, status)
                    VALUES (NOW(), %s, 'RUNNING')
                    RETURNING session_id
                """, (initial_balance,))
                
                result = cursor.fetchone()
                self.session_id = result['session_id']
                logger.info(f"✅ Sesión de trading iniciada - ID: {self.session_id}")
                return self.session_id
                
        except Exception as e:
            logger.error(f"Error iniciando sesión: {e}")
            return None
    
    def save_trade_open(self, trade_data: Dict[str, Any]) -> Optional[int]:
        """Guarda una operación abierta"""
        try:
            with self.db.get_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO trades (
                        session_id, deal_reference, epic, direction,
                        entry_time, entry_price, position_size,
                        stop_loss, take_profit, margin_used,
                        confidence, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'OPEN'
                    ) RETURNING trade_id
                """, (
                    self.session_id,
                    trade_data.get('deal_reference'),
                    trade_data['epic'],
                    trade_data['direction'],
                    trade_data.get('entry_time', datetime.now()),
                    trade_data['entry_price'],
                    trade_data['position_size'],
                    trade_data.get('stop_loss'),
                    trade_data.get('take_profit'),
                    trade_data.get('margin_used', 0),
                    trade_data.get('confidence', 0)
                ))
                
                result = cursor.fetchone()
                logger.info(f"✅ Trade guardado - ID: {result['trade_id']}")
                return result['trade_id']
                
        except Exception as e:
            logger.error(f"Error guardando trade: {e}")
            return None
    
    def close_trade(self, deal_reference: str, exit_price: float, 
                   exit_reason: str = 'MANUAL') -> bool:
        """Cierra una operación"""
        try:
            with self.db.get_cursor(commit=True) as cursor:
                # Primero obtener info del trade
                cursor.execute("""
                    SELECT entry_price, position_size, direction
                    FROM trades 
                    WHERE deal_reference = %s AND status = 'OPEN'
                """, (deal_reference,))
                
                trade = cursor.fetchone()
                if not trade:
                    logger.warning(f"Trade no encontrado: {deal_reference}")
                    return False
                
                # Calcular P&L
                if trade['direction'] == 'BUY':
                    pnl = (exit_price - trade['entry_price']) * trade['position_size']
                else:  # SELL
                    pnl = (trade['entry_price'] - exit_price) * trade['position_size']
                
                pnl_percent = (pnl / (trade['entry_price'] * trade['position_size'])) * 100
                
                # Actualizar trade
                cursor.execute("""
                    UPDATE trades SET
                        exit_time = NOW(),
                        exit_price = %s,
                        exit_reason = %s,
                        pnl = %s,
                        pnl_percent = %s,
                        status = 'CLOSED',
                        updated_at = NOW()
                    WHERE deal_reference = %s
                    RETURNING trade_id
                """, (exit_price, exit_reason, pnl, pnl_percent, deal_reference))
                
                result = cursor.fetchone()
                logger.info(f"✅ Trade cerrado - ID: {result['trade_id']} | P&L: €{pnl:.2f}")
                
                # Actualizar contador de sesión
                if self.session_id:
                    cursor.execute("""
                        UPDATE trading_sessions 
                        SET total_trades = total_trades + 1,
                            total_pnl = total_pnl + %s
                        WHERE session_id = %s
                    """, (pnl, self.session_id))
                
                return True
                
        except Exception as e:
            logger.error(f"Error cerrando trade: {e}")
            return False
    
    def save_account_snapshot(self, account_data: Dict[str, Any]) -> bool:
        """Guarda un snapshot del estado de la cuenta"""
        try:
            with self.db.get_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO account_snapshots (
                        session_id, balance, available, 
                        margin_used, margin_percent, 
                        open_positions_count, total_pnl
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.session_id,
                    account_data['balance'],
                    account_data['available'],
                    account_data['margin_used'],
                    account_data.get('margin_percent', 0),
                    account_data.get('open_positions_count', 0),
                    account_data.get('total_pnl', 0)
                ))
                return True
                
        except Exception as e:
            logger.error(f"Error guardando snapshot: {e}")
            return False
    
    def get_trades_history(self, limit: int = 50) -> List[Dict]:
        """Obtiene historial de trades"""
        try:
            with self.db.get_cursor(commit=False) as cursor:
                cursor.execute("""
                    SELECT 
                        trade_id,
                        deal_reference,
                        epic,
                        direction,
                        entry_time,
                        entry_price,
                        position_size,
                        exit_time,
                        exit_price,
                        pnl,
                        pnl_percent,
                        status,
                        exit_reason
                    FROM trades
                    ORDER BY entry_time DESC
                    LIMIT %s
                """, (limit,))
                
                trades = cursor.fetchall()
                return trades or []
                
        except Exception as e:
            logger.error(f"Error obteniendo historial: {e}")
            return []
    
    def get_active_trades(self) -> List[Dict]:
        """Obtiene trades activos"""
        try:
            with self.db.get_cursor(commit=False) as cursor:
                cursor.execute("""
                    SELECT * FROM trades
                    WHERE status = 'OPEN'
                    ORDER BY entry_time DESC
                """)
                
                return cursor.fetchall() or []
                
        except Exception as e:
            logger.error(f"Error obteniendo trades activos: {e}")
            return []
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la sesión actual"""
        if not self.session_id:
            return {}
        
        try:
            with self.db.get_cursor(commit=False) as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                        COUNT(CASE WHEN pnl < 0 THEN 1 END) as losing_trades,
                        COALESCE(SUM(pnl), 0) as total_pnl,
                        COALESCE(AVG(pnl), 0) as avg_pnl,
                        COALESCE(MAX(pnl), 0) as best_trade,
                        COALESCE(MIN(pnl), 0) as worst_trade
                    FROM trades
                    WHERE session_id = %s AND status = 'CLOSED'
                """, (self.session_id,))
                
                stats = cursor.fetchone()
                
                # Calcular win rate
                if stats and stats['total_trades'] > 0:
                    stats['win_rate'] = (stats['winning_trades'] / stats['total_trades']) * 100
                else:
                    stats['win_rate'] = 0
                
                return dict(stats) if stats else {}
                
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}
    
    def end_session(self, final_balance: float) -> bool:
        """Finaliza la sesión de trading"""
        if not self.session_id:
            return False
        
        try:
            with self.db.get_cursor(commit=True) as cursor:
                cursor.execute("""
                    UPDATE trading_sessions SET
                        end_time = NOW(),
                        final_balance = %s,
                        status = 'COMPLETED'
                    WHERE session_id = %s
                """, (final_balance, self.session_id))
                
                logger.info(f"✅ Sesión finalizada - ID: {self.session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error finalizando sesión: {e}")
            return False