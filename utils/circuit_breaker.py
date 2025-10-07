"""
Circuit Breaker - Sistema de protección contra pérdidas excesivas
Detiene el trading automáticamente cuando se alcanzan límites de riesgo
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from config import Config

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Sistema de Circuit Breaker para protección del capital
    
    Monitorea y detiene el trading cuando:
    - Pérdida diaria excede el límite
    - Pérdida semanal excede el límite
    - Pérdidas consecutivas exceden el límite
    - Drawdown total excede el límite
    """
    
    def __init__(self):
        self.initial_balance: Optional[float] = None
        self.current_balance: Optional[float] = None
        self.peak_balance: Optional[float] = None
        
        # Tracking de pérdidas
        self.daily_start_balance: Optional[float] = None
        self.weekly_start_balance: Optional[float] = None
        self.last_reset_date: Optional[datetime] = None
        self.week_start_date: Optional[datetime] = None
        
        # Contador de pérdidas consecutivas
        self.consecutive_losses: int = 0
        
        # Estado del circuit breaker
        self.is_active_flag: bool = False
        self.activation_reason: Optional[str] = None
        self.activation_time: Optional[datetime] = None
    
    def initialize(self, starting_balance: float):
        """
        Inicializa el circuit breaker con el balance inicial
        
        Args:
            starting_balance: Balance actual de la cuenta
        """
        self.initial_balance = starting_balance
        self.current_balance = starting_balance
        self.peak_balance = starting_balance
        
        self.daily_start_balance = starting_balance
        self.weekly_start_balance = starting_balance
        self.last_reset_date = datetime.now()
        self.week_start_date = datetime.now()
        
        self.consecutive_losses = 0
        self.is_active_flag = False
        self.activation_reason = None
        
        logger.info(f"🛡️  Circuit Breaker inicializado - Balance: €{starting_balance:.2f}")
    
    def update_current_balance(self, new_balance: float):
        """
        Actualiza el balance actual y verifica límites
        
        Args:
            new_balance: Nuevo balance de la cuenta
        """
        if not Config.ENABLE_CIRCUIT_BREAKER:
            return
        
        if self.current_balance is None:
            self.initialize(new_balance)
            return
        
        old_balance = self.current_balance
        self.current_balance = new_balance
        
        # Actualizar peak si es nuevo máximo
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
        
        # Reset diario
        self._check_daily_reset()
        
        # Reset semanal
        self._check_weekly_reset()
        
        # Verificar límites
        self._check_limits()
        
        # Log de cambio de balance
        change = new_balance - old_balance
        if abs(change) > 0.01:  # Solo log si hay cambio significativo
            logger.debug(f"💰 Balance actualizado: €{new_balance:.2f} (cambio: €{change:+.2f})")
    
    def register_trade_result(self, pnl: float):
        """
        Registra el resultado de un trade para tracking de rachas
        
        Args:
            pnl: P&L del trade (positivo = ganancia, negativo = pérdida)
        """
        if pnl < 0:
            self.consecutive_losses += 1
            logger.debug(f"📉 Pérdida consecutiva #{self.consecutive_losses}")
        else:
            if self.consecutive_losses > 0:
                logger.debug(f"✅ Racha de pérdidas rota después de {self.consecutive_losses} trades")
            self.consecutive_losses = 0
    
    def _check_daily_reset(self):
        """Verifica si debe resetear el tracking diario"""
        now = datetime.now()
        
        if self.last_reset_date is None:
            self.last_reset_date = now
            return
        
        # Si cambió el día, resetear
        if now.date() > self.last_reset_date.date():
            logger.info(f"📅 Nuevo día - Reseteando tracking diario")
            self.daily_start_balance = self.current_balance
            self.last_reset_date = now
    
    def _check_weekly_reset(self):
        """Verifica si debe resetear el tracking semanal"""
        now = datetime.now()
        
        if self.week_start_date is None:
            self.week_start_date = now
            return
        
        # Si pasó 1 semana (7 días)
        days_since_start = (now - self.week_start_date).days
        if days_since_start >= 7:
            logger.info(f"📅 Nueva semana - Reseteando tracking semanal")
            self.weekly_start_balance = self.current_balance
            self.week_start_date = now
    
    def _check_limits(self):
        """Verifica todos los límites y activa circuit breaker si es necesario"""
        if self.is_active_flag:
            return  # Ya está activo
        
        # 1. Pérdida diaria
        if self.daily_start_balance and self.current_balance:
            daily_loss_percent = ((self.current_balance - self.daily_start_balance) / 
                                 self.daily_start_balance) * 100
            
            if daily_loss_percent <= -Config.MAX_DAILY_LOSS_PERCENT:
                self._activate(
                    f"Pérdida diaria excedida: {daily_loss_percent:.2f}% "
                    f"(límite: -{Config.MAX_DAILY_LOSS_PERCENT}%)"
                )
                return
        
        # 2. Pérdida semanal
        if self.weekly_start_balance and self.current_balance:
            weekly_loss_percent = ((self.current_balance - self.weekly_start_balance) / 
                                  self.weekly_start_balance) * 100
            
            if weekly_loss_percent <= -Config.MAX_WEEKLY_LOSS_PERCENT:
                self._activate(
                    f"Pérdida semanal excedida: {weekly_loss_percent:.2f}% "
                    f"(límite: -{Config.MAX_WEEKLY_LOSS_PERCENT}%)"
                )
                return
        
        # 3. Pérdidas consecutivas
        if self.consecutive_losses >= Config.MAX_CONSECUTIVE_LOSSES:
            self._activate(
                f"Pérdidas consecutivas excedidas: {self.consecutive_losses} "
                f"(límite: {Config.MAX_CONSECUTIVE_LOSSES})"
            )
            return
        
        # 4. Drawdown total desde peak
        if self.peak_balance and self.current_balance:
            drawdown_percent = ((self.peak_balance - self.current_balance) / 
                               self.peak_balance) * 100
            
            if drawdown_percent >= Config.MAX_TOTAL_DRAWDOWN_PERCENT:
                self._activate(
                    f"Drawdown total excedido: {drawdown_percent:.2f}% "
                    f"(límite: {Config.MAX_TOTAL_DRAWDOWN_PERCENT}%)"
                )
                return
    
    def _activate(self, reason: str):
        """
        Activa el circuit breaker
        
        Args:
            reason: Razón de la activación
        """
        self.is_active_flag = True
        self.activation_reason = reason
        self.activation_time = datetime.now()
        
        logger.critical("="*80)
        logger.critical("🚨 CIRCUIT BREAKER ACTIVADO 🚨")
        logger.critical("="*80)
        logger.critical(f"Razón: {reason}")
        logger.critical(f"Balance actual: €{self.current_balance:.2f}")
        logger.critical(f"Peak balance: €{self.peak_balance:.2f}")
        logger.critical(f"Balance inicial: €{self.initial_balance:.2f}")
        logger.critical("="*80)
        logger.critical("⛔ EL BOT NO EJECUTARÁ MÁS OPERACIONES")
        logger.critical("="*80)
    
    def is_active(self) -> bool:
        """
        Verifica si el circuit breaker está activo
        
        Returns:
            True si está activo (no se debe operar)
        """
        if not Config.ENABLE_CIRCUIT_BREAKER:
            return False
        
        return self.is_active_flag
    
    def get_status(self) -> Dict:
        """
        Obtiene el estado completo del circuit breaker
        
        Returns:
            Dict con información del estado
        """
        status = {
            'enabled': Config.ENABLE_CIRCUIT_BREAKER,
            'is_active': self.is_active_flag,
            'reason': self.activation_reason,
            'activation_time': self.activation_time.isoformat() if self.activation_time else None,
            'current_balance': self.current_balance,
            'initial_balance': self.initial_balance,
            'peak_balance': self.peak_balance,
            'consecutive_losses': self.consecutive_losses,
        }
        
        # Calcular métricas actuales
        if self.daily_start_balance and self.current_balance:
            status['daily_loss_percent'] = (
                (self.current_balance - self.daily_start_balance) / 
                self.daily_start_balance
            ) * 100
        
        if self.weekly_start_balance and self.current_balance:
            status['weekly_loss_percent'] = (
                (self.current_balance - self.weekly_start_balance) / 
                self.weekly_start_balance
            ) * 100
        
        if self.peak_balance and self.current_balance:
            status['current_drawdown_percent'] = (
                (self.peak_balance - self.current_balance) / 
                self.peak_balance
            ) * 100
        
        # Mensaje descriptivo
        if self.is_active_flag:
            status['message'] = f"⛔ ACTIVADO: {self.activation_reason}"
        else:
            status['message'] = "✅ Sistema operando normalmente"
        
        return status
    
    def reset(self):
        """
        Resetea el circuit breaker (usar con precaución)
        SOLO debe usarse manualmente por el operador
        """
        logger.warning("⚠️  RESETEANDO CIRCUIT BREAKER MANUALMENTE")
        self.is_active_flag = False
        self.activation_reason = None
        self.activation_time = None
        self.consecutive_losses = 0
        logger.info("✅ Circuit Breaker reseteado")