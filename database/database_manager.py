"""
Gestor de base de datos para el trading bot
Maneja todas las operaciones de persistencia
"""

import logging
import json
from datetime import datetime
from typing import Dict, Optional, List
from database.connection import DatabaseConnection
from database.models import TradingSession, Trade, MarketSignal, AccountSnapshot

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestiona todas las operaciones con la base de datos"""
    
    def __init__(self):
        try:
            self.db = DatabaseConnection()
            self.current_session_id: Optional[int] = None
            logger.info("✅ DatabaseManager inicializado")
        except Exception as e:
            logger.warning(f"⚠️  Base de datos no disponible: {e}")
            self.db = None
            self.current_session_id = None
    
    def has_active_session(self) -> bool:
        """Verifica si hay una sesión activa"""
        return self.current_session_id is not None and self.db is not None
    
    # ============================================
    # SESIONES
    # ============================================
    
    def start_session(self, initial_balance: float, config_snapshot: dict) -> Optional[int]:
        """
        Inicia una nueva sesión de trading
        
        Args:
            initial_balance: Balance inicial de la cuenta
            config_snapshot: Configuración actual del bot
            
        Returns:
            int: ID de la sesión creada, o None si falla
        """
        if not self.db:
            logger.debug("BD no disponible, sesión no iniciada")
            return None
        
        try:
            session = TradingSession(
                start_time=datetime.now(),
                initial_balance=initial_balance,
                config_snapshot=config_snapshot
            )
            
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO trading_sessions 
                    (start_time, initial_balance, config_snapshot, status)
                    VALUES (%s, %s, %s, 'RUNNING')
                    RETURNING session_id
                """, (
                    session.start_time,
                    session.initial_balance,
                    json.dumps(session.config_snapshot)
                ))
                
                result = cursor.fetchone()
                self.current_session_id = result['session_id']
                
                logger.info(f"✅ Sesión de trading iniciada - ID: {self.current_session_id}")
                return self.current_session_id
                
        except Exception as e:
            logger.error(f"Error iniciando sesión: {e}")
            return None
    
    def end_session(self, final_balance: float):
        """
        Finaliza la sesión actual
        
        Args:
            final_balance: Balance final de la cuenta
        """
        if not self.has_active_session():
            return
        
        try:
            with self.db.get_cursor() as cursor:
                # Calcular estadísticas
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                        COALESCE(SUM(pnl), 0) as total_pnl
                    FROM trades
                    WHERE session_id = %s AND status = 'CLOSED'
                """, (self.current_session_id,))
                
                stats = cursor.fetchone()
                
                # Actualizar sesión
                cursor.execute("""
                    UPDATE trading_sessions
                    SET 
                        end_time = %s,
                        final_balance = %s,
                        total_trades = %s,
                        winning_trades = %s,
                        losing_trades = %s,
                        total_pnl = %s,
                        status = 'COMPLETED'
                    WHERE session_id = %s
                """, (
                    datetime.now(),
                    final_balance,
                    stats['total_trades'],
                    stats['wins'],
                    stats['losses'],
                    stats['total_pnl'],
                    self.current_session_id
                ))
            
            logger.info(f"✅ Sesión finalizada - ID: {self.current_session_id}")
            self.current_session_id = None
            
        except Exception as e:
            logger.error(f"Error finalizando sesión: {e}")
    
    # ============================================
    # SEÑALES DE MERCADO
    # ============================================
    
    def save_signal(self, analysis: Dict) -> Optional[int]:
        """
        Guarda una señal de mercado
        
        Args:
            analysis: Resultado del análisis de la estrategia
            
        Returns:
            int: ID de la señal guardada, o None si falla
        """
        if not self.has_active_session():
            return None
        
        try:
            indicators = analysis.get('indicators', {})
            
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO market_signals (
                        session_id, epic, signal, confidence, current_price,
                        rsi, macd, macd_signal, macd_hist,
                        sma_short, sma_long, momentum,
                        atr_percent, adx, plus_di, minus_di,
                        slow_trend, reasons, indicators_json
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    RETURNING signal_id
                """, (
                    self.current_session_id,
                    analysis['epic'],
                    analysis['signal'],
                    analysis['confidence'],
                    analysis['current_price'],
                    indicators.get('rsi'),
                    indicators.get('macd'),
                    indicators.get('macd_signal'),
                    indicators.get('macd_hist'),
                    indicators.get('sma_short'),
                    indicators.get('sma_long'),
                    indicators.get('momentum'),
                    analysis.get('atr_percent'),
                    analysis.get('adx'),
                    indicators.get('plus_di'),
                    indicators.get('minus_di'),
                    analysis.get('slow_trend'),
                    analysis.get('reasons', []),
                    json.dumps(indicators)
                ))
                
                result = cursor.fetchone()
                return result['signal_id']
                
        except Exception as e:
            logger.debug(f"Error guardando señal: {e}")
            return None
    
    def mark_signal_executed(self, signal_id: int, trade_id: int):
        """Marca una señal como ejecutada"""
        if not self.has_active_session():
            return
        
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE market_signals
                    SET executed = TRUE, trade_id = %s
                    WHERE signal_id = %s
                """, (trade_id, signal_id))
        except Exception as e:
            logger.debug(f"Error marcando señal ejecutada: {e}")
    
    # ============================================
    # TRADES
    # ============================================
    
    def save_trade_open(self, trade_data: Dict) -> Optional[int]:
        """
        Guarda un trade abierto
        
        Args:
            trade_data: Datos del trade
            
        Returns:
            int: ID del trade guardado, o None si falla
        """
        if not self.has_active_session():
            return None
        
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO trades (
                        session_id, signal_id, deal_reference,
                        epic, direction, entry_time, entry_price,
                        position_size, stop_loss, take_profit,
                        margin_used, confidence, sl_tp_mode, atr_at_entry,
                        entry_reasons, status
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, 'OPEN'
                    )
                    RETURNING trade_id
                """, (
                    self.current_session_id,
                    trade_data.get('signal_id'),
                    trade_data.get('deal_reference'),
                    trade_data['epic'],
                    trade_data['direction'],
                    datetime.now(),
                    trade_data['entry_price'],
                    trade_data['size'],
                    trade_data['stop_loss'],
                    trade_data['take_profit'],
                    trade_data['margin_est'],
                    trade_data.get('confidence'),
                    trade_data.get('sl_tp_mode'),
                    trade_data.get('atr_percent'),
                    trade_data.get('reasons', [])
                ))
                
                result = cursor.fetchone()
                return result['trade_id']
                
        except Exception as e:
            logger.error(f"Error guardando trade: {e}")
            return None
    
    def save_trade_close(self, deal_id: str, exit_data: Dict):
        """
        Actualiza un trade cuando se cierra
        
        Args:
            deal_id: ID del deal en Capital.com
            exit_data: Datos de cierre del trade
        """
        if not self.has_active_session():
            return
        
        try:
            entry_time = exit_data.get('entry_time')
            exit_time = exit_data.get('exit_time', datetime.now())
            
            duration_minutes = None
            if entry_time and exit_time:
                duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
            
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE trades
                    SET 
                        exit_time = %s,
                        exit_price = %s,
                        exit_reason = %s,
                        pnl = %s,
                        pnl_percent = %s,
                        duration_minutes = %s,
                        status = 'CLOSED',
                        updated_at = %s
                    WHERE deal_reference = %s AND session_id = %s
                """, (
                    exit_time,
                    exit_data.get('exit_price'),
                    exit_data.get('exit_reason'),
                    exit_data.get('pnl'),
                    exit_data.get('pnl_percent'),
                    duration_minutes,
                    datetime.now(),
                    deal_id,
                    self.current_session_id
                ))
                
        except Exception as e:
            logger.error(f"Error actualizando trade cerrado: {e}")
    
    # ============================================
    # SNAPSHOTS DE CUENTA
    # ============================================
    
    def save_account_snapshot(self, account_data: Dict):
        """
        Guarda un snapshot del estado de la cuenta
        
        Args:
            account_data: Datos de la cuenta
        """
        if not self.has_active_session():
            return
        
        try:
            balance = account_data['balance']
            available = account_data['available']
            margin_used = balance - available
            margin_percent = (margin_used / balance) if balance > 0 else 0
            
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO account_snapshots (
                        session_id, balance, available,
                        margin_used, margin_percent, open_positions_count
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    self.current_session_id,
                    balance,
                    available,
                    margin_used,
                    margin_percent,
                    account_data.get('open_positions', 0)
                ))
                
        except Exception as e:
            logger.debug(f"Error guardando snapshot: {e}")