"""
Gestión de riesgo y circuit breaker
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Métricas de riesgo actuales"""
    daily_loss: float = 0
    weekly_loss: float = 0
    consecutive_losses: int = 0
    max_drawdown: float = 0
    positions_open: int = 0
    margin_used: float = 0
    last_updated: datetime = field(default_factory=datetime.now)


class RiskManager:
    """Gestiona el riesgo y circuit breaker"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.initial_balance = 0
        self.current_balance = 0
        self.peak_balance = 0
        self.metrics = RiskMetrics()
        self.trade_history = deque(maxlen=100)
        self.is_active = True
        
        # Límites
        self.max_daily_loss_pct = config.get('MAX_DAILY_LOSS_PERCENT', 3.0)
        self.max_weekly_loss_pct = config.get('MAX_WEEKLY_LOSS_PERCENT', 8.0)
        self.max_consecutive_losses = config.get('MAX_CONSECUTIVE_LOSSES', 5)
        self.max_drawdown_pct = config.get('MAX_TOTAL_DRAWDOWN_PERCENT', 15.0)
        self.max_positions = config.get('MAX_POSITIONS', 8)
        self.max_margin_pct = config.get('MAX_CAPITAL_RISK', 70.0)
    
    def initialize(self, balance: float):
        """Inicializa con el balance inicial"""
        self.initial_balance = balance
        self.current_balance = balance
        self.peak_balance = balance
        logger.info(f"🛡️ RiskManager inicializado - Balance: €{balance:.2f}")
    
    def check_trade_allowed(self, signal: Dict[str, Any]) -> tuple[bool, str]:
        """Verifica si se permite abrir una nueva operación"""
        
        if not self.is_active:
            return False, "Circuit breaker activado"
        
        # Check 1: Número máximo de posiciones
        if self.metrics.positions_open >= self.max_positions:
            return False, f"Máximo de posiciones alcanzado ({self.max_positions})"
        
        # Check 2: Margen disponible
        margin_required = signal.get('size', 0) * signal.get('price', 0) * 0.2
        total_margin = self.metrics.margin_used + margin_required
        margin_pct = (total_margin / self.current_balance) * 100
        
        if margin_pct > self.max_margin_pct:
            return False, f"Margen excedería límite ({margin_pct:.1f}% > {self.max_margin_pct}%)"
        
        # Check 3: Pérdida diaria
        if abs(self.metrics.daily_loss) >= self.max_daily_loss_pct:
            return False, f"Pérdida diaria máxima alcanzada ({self.metrics.daily_loss:.1f}%)"
        
        # Check 4: Pérdidas consecutivas
        if self.metrics.consecutive_losses >= self.max_consecutive_losses:
            return False, f"Demasiadas pérdidas consecutivas ({self.metrics.consecutive_losses})"
        
        # Check 5: Drawdown
        if self.metrics.max_drawdown >= self.max_drawdown_pct:
            return False, f"Drawdown máximo alcanzado ({self.metrics.max_drawdown:.1f}%)"
        
        return True, "OK"
    
    def update_trade_result(self, pnl: float):
        """Actualiza métricas después de cerrar un trade"""
        
        # Actualizar balance
        self.current_balance += pnl
        
        # Actualizar peak para drawdown
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        # Calcular drawdown
        drawdown = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        self.metrics.max_drawdown = max(self.metrics.max_drawdown, drawdown)
        
        # Actualizar pérdidas consecutivas
        if pnl < 0:
            self.metrics.consecutive_losses += 1
        else:
            self.metrics.consecutive_losses = 0
        
        # Actualizar pérdida diaria (simplificado)
        daily_pnl_pct = (pnl / self.initial_balance) * 100
        self.metrics.daily_loss += daily_pnl_pct
        
        # Agregar a historial
        self.trade_history.append({
            'pnl': pnl,
            'timestamp': datetime.now(),
            'balance': self.current_balance
        })
        
        # Verificar si activar circuit breaker
        self._check_circuit_breaker()
        
        logger.info(f"📊 Balance: €{self.current_balance:.2f} | "
                   f"Drawdown: {drawdown:.1f}% | "
                   f"Losses: {self.metrics.consecutive_losses}")
    
    def _check_circuit_breaker(self):
        """Verifica si debe activarse el circuit breaker"""
        
        triggers = []
        
        if abs(self.metrics.daily_loss) >= self.max_daily_loss_pct:
            triggers.append(f"Pérdida diaria: {self.metrics.daily_loss:.1f}%")
        
        if self.metrics.consecutive_losses >= self.max_consecutive_losses:
            triggers.append(f"Pérdidas consecutivas: {self.metrics.consecutive_losses}")
        
        if self.metrics.max_drawdown >= self.max_drawdown_pct:
            triggers.append(f"Drawdown: {self.metrics.max_drawdown:.1f}%")
        
        if triggers:
            self.is_active = False
            logger.warning(f"🛑 CIRCUIT BREAKER ACTIVADO: {', '.join(triggers)}")
    
    def reset_daily_metrics(self):
        """Resetea métricas diarias"""
        self.metrics.daily_loss = 0
        logger.info("📅 Métricas diarias reseteadas")
    
    def get_position_size(self, signal: Dict[str, Any], 
                         available_margin: float) -> float:
        """Calcula el tamaño de posición apropiado"""
        
        # Kelly Criterion simplificado o fixed fractional
        confidence = signal.get('confidence', 0.5)
        
        # Riesgo por trade: 2-3% del balance
        risk_per_trade = self.current_balance * 0.02
        
        # Calcular basado en stop loss
        price = signal.get('price', 0)
        stop_loss = signal.get('stop_loss', 0)
        
        if price and stop_loss:
            risk_points = abs(price - stop_loss)
            if risk_points > 0:
                position_size = risk_per_trade / risk_points
                
                # Ajustar por confianza
                position_size *= confidence
                
                # Limitar al margen disponible
                max_size = available_margin / (price * 0.2)  # 20% margen
                position_size = min(position_size, max_size)
                
                return round(position_size, 2)
        
        return 0.1  # Tamaño mínimo por defecto