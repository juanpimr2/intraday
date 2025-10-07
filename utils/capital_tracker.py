"""
Capital Tracker - Gestión inteligente de capital diario
Distribuye el capital disponible a lo largo de la semana y prioriza por confianza
"""

import logging
from datetime import datetime, date
from typing import Optional, Dict, List
from config import Config

logger = logging.getLogger(__name__)


class CapitalTracker:
    """
    Gestor de capital diario con distribución semanal
    
    Funcionalidad:
    - Divide el capital semanal en 5 días de trading
    - Trackea cuánto capital se ha usado hoy
    - Resetea automáticamente cada día
    - Prioriza operaciones por confianza
    """
    
    def __init__(self):
        self.current_date: Optional[date] = None
        self.capital_used_today: float = 0.0
        self.daily_limit: float = 0.0
        self.available_capital: float = 0.0
        
        # Histórico del día
        self.today_trades: List[Dict] = []
        
        # Estado de inicialización
        self.is_initialized: bool = False
    
    def initialize(self, available_balance: float):
        """
        Inicializa el tracker con el capital disponible
        
        Args:
            available_balance: Balance disponible en la cuenta
        """
        self.available_capital = available_balance
        self.current_date = datetime.now().date()
        
        # Calcular límite diario basado en configuración
        # Capital semanal total = TARGET_PERCENT_OF_AVAILABLE
        # Distribuido en 5 días de trading
        weekly_capital = available_balance * Config.TARGET_PERCENT_OF_AVAILABLE
        self.daily_limit = weekly_capital / Config.TRADING_DAYS_PER_WEEK
        
        self.capital_used_today = 0.0
        self.today_trades = []
        self.is_initialized = True
        
        logger.info("="*70)
        logger.info("💰 CAPITAL TRACKER INICIALIZADO")
        logger.info("="*70)
        logger.info(f"Balance disponible: €{available_balance:,.2f}")
        logger.info(f"Capital semanal objetivo: €{weekly_capital:,.2f} ({Config.TARGET_PERCENT_OF_AVAILABLE*100:.0f}%)")
        logger.info(f"Límite diario: €{self.daily_limit:,.2f} ({(self.daily_limit/available_balance)*100:.1f}%)")
        logger.info(f"Días de trading por semana: {Config.TRADING_DAYS_PER_WEEK}")
        logger.info("="*70)
    
    def update_available_balance(self, new_balance: float):
        """
        Actualiza el balance disponible y recalcula límites
        
        Args:
            new_balance: Nuevo balance disponible
        """
        if not self.is_initialized:
            self.initialize(new_balance)
            return
        
        self.available_capital = new_balance
        
        # Recalcular límite diario
        weekly_capital = new_balance * Config.TARGET_PERCENT_OF_AVAILABLE
        self.daily_limit = weekly_capital / Config.TRADING_DAYS_PER_WEEK
        
        logger.debug(f"💰 Balance actualizado: €{new_balance:,.2f} | Límite diario: €{self.daily_limit:,.2f}")
    
    def check_and_reset_daily(self):
        """
        Verifica si cambió el día y resetea el tracking diario
        """
        if not self.is_initialized:
            return
        
        today = datetime.now().date()
        
        # Si cambió el día, resetear
        if today > self.current_date:
            logger.info("="*70)
            logger.info(f"📅 NUEVO DÍA DE TRADING: {today.strftime('%Y-%m-%d')}")
            logger.info("="*70)
            logger.info(f"Capital usado ayer: €{self.capital_used_today:,.2f}")
            logger.info(f"Trades ejecutados ayer: {len(self.today_trades)}")
            logger.info(f"Límite diario renovado: €{self.daily_limit:,.2f}")
            logger.info("="*70)
            
            # Resetear tracking
            self.current_date = today
            self.capital_used_today = 0.0
            self.today_trades = []
    
    def get_available_capital_today(self) -> float:
        """
        Obtiene el capital disponible para operar hoy
        
        Returns:
            float: Capital disponible restante para hoy
        """
        if not self.is_initialized:
            logger.warning("⚠️  Capital Tracker no inicializado")
            return 0.0
        
        # Verificar reset diario
        self.check_and_reset_daily()
        
        # Capital disponible = límite diario - usado hoy
        remaining = max(self.daily_limit - self.capital_used_today, 0.0)
        
        return remaining
    
    def can_trade_today(self) -> bool:
        """
        Verifica si todavía se puede operar hoy
        
        Returns:
            bool: True si hay capital disponible
        """
        remaining = self.get_available_capital_today()
        return remaining > 0
    
    def allocate_capital(self, amount: float, epic: str, confidence: float) -> bool:
        """
        Intenta asignar capital para una operación
        
        Args:
            amount: Cantidad de capital a asignar
            epic: Activo a operar
            confidence: Confianza de la señal (0-1)
            
        Returns:
            bool: True si se pudo asignar, False si excede límite
        """
        if not self.is_initialized:
            logger.warning("⚠️  Capital Tracker no inicializado")
            return False
        
        # Verificar reset diario
        self.check_and_reset_daily()
        
        # Verificar si hay suficiente capital disponible
        available = self.get_available_capital_today()
        
        if amount > available:
            logger.warning(
                f"⛔ Capital insuficiente para {epic}: "
                f"Requiere €{amount:.2f}, Disponible hoy: €{available:.2f}"
            )
            return False
        
        # Asignar capital
        self.capital_used_today += amount
        
        # Registrar trade
        self.today_trades.append({
            'epic': epic,
            'amount': amount,
            'confidence': confidence,
            'timestamp': datetime.now()
        })
        
        logger.info(
            f"✅ Capital asignado: €{amount:.2f} para {epic} "
            f"(Confianza: {confidence:.0%}) | "
            f"Usado hoy: €{self.capital_used_today:.2f}/{self.daily_limit:.2f}"
        )
        
        return True
    
    def get_status(self) -> Dict:
        """
        Obtiene el estado actual del capital tracker
        
        Returns:
            Dict con información del estado
        """
        if not self.is_initialized:
            return {
                'initialized': False,
                'message': 'Capital Tracker no inicializado'
            }
        
        # Verificar reset diario
        self.check_and_reset_daily()
        
        available_today = self.get_available_capital_today()
        usage_percent = (self.capital_used_today / self.daily_limit * 100) if self.daily_limit > 0 else 0
        
        return {
            'initialized': True,
            'current_date': self.current_date.isoformat(),
            'daily_limit': self.daily_limit,
            'capital_used_today': self.capital_used_today,
            'available_today': available_today,
            'usage_percent': usage_percent,
            'trades_today': len(self.today_trades),
            'can_trade': self.can_trade_today(),
            'available_capital': self.available_capital
        }
    
    def get_daily_summary(self) -> Dict:
        """
        Obtiene un resumen del día actual
        
        Returns:
            Dict con resumen del día
        """
        status = self.get_status()
        
        if not status['initialized']:
            return status
        
        # Calcular estadísticas de trades del día
        total_trades = len(self.today_trades)
        avg_confidence = 0.0
        
        if total_trades > 0:
            avg_confidence = sum(t['confidence'] for t in self.today_trades) / total_trades
        
        return {
            **status,
            'summary': {
                'total_trades_today': total_trades,
                'average_confidence': avg_confidence,
                'total_allocated': self.capital_used_today,
                'remaining_for_today': status['available_today']
            }
        }
    
    def prioritize_signals(self, signals: List[Dict]) -> List[Dict]:
        """
        Ordena señales por confianza (mayor a menor)
        
        Args:
            signals: Lista de análisis con campo 'confidence'
            
        Returns:
            Lista ordenada por confianza descendente
        """
        if not signals:
            return []
        
        # Ordenar por confianza (mayor primero)
        sorted_signals = sorted(
            signals,
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )
        
        logger.info("📊 Señales priorizadas por confianza:")
        for i, signal in enumerate(sorted_signals, 1):
            logger.info(
                f"  {i}. {signal.get('epic', 'N/A')}: "
                f"{signal.get('signal', 'N/A')} "
                f"(Confianza: {signal.get('confidence', 0):.0%})"
            )
        
        return sorted_signals
    
    def log_daily_usage(self):
        """
        Log del uso diario de capital (para debugging)
        """
        if not self.is_initialized:
            return
        
        self.check_and_reset_daily()
        
        logger.info("\n" + "="*70)
        logger.info("📊 USO DE CAPITAL DIARIO")
        logger.info("="*70)
        logger.info(f"Fecha: {self.current_date}")
        logger.info(f"Límite diario: €{self.daily_limit:,.2f}")
        logger.info(f"Capital usado: €{self.capital_used_today:,.2f}")
        logger.info(f"Capital disponible: €{self.get_available_capital_today():,.2f}")
        logger.info(f"Utilización: {(self.capital_used_today/self.daily_limit)*100:.1f}%")
        logger.info(f"Trades hoy: {len(self.today_trades)}")
        
        if self.today_trades:
            logger.info("\nDetalles de trades:")
            for i, trade in enumerate(self.today_trades, 1):
                logger.info(
                    f"  {i}. {trade['epic']}: €{trade['amount']:.2f} "
                    f"(Conf: {trade['confidence']:.0%}) @ {trade['timestamp'].strftime('%H:%M:%S')}"
                )
        
        logger.info("="*70 + "\n")