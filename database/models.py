# database/models.py
"""
Modelos de datos para la base de datos - SIMPLIFICADO
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

@dataclass
class TradingSession:
    """Modelo de sesión de trading"""
    session_id: Optional[int] = None
    start_time: datetime = None
    end_time: Optional[datetime] = None
    initial_balance: float = 0.0
    final_balance: Optional[float] = None
    total_trades: int = 0
    total_pnl: float = 0.0
    status: str = 'RUNNING'
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Trade:
    """Modelo de operación"""
    trade_id: Optional[int] = None
    session_id: Optional[int] = None
    deal_reference: str = None
    epic: str = None
    direction: str = None
    entry_time: datetime = None
    entry_price: float = 0.0
    position_size: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    margin_used: float = 0.0
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    status: str = 'OPEN'
    confidence: Optional[float] = None
    
    def to_dict(self):
        return asdict(self)

@dataclass
class AccountSnapshot:
    """Modelo de snapshot de cuenta"""
    snapshot_id: Optional[int] = None
    session_id: Optional[int] = None
    timestamp: datetime = None
    balance: float = 0.0
    available: float = 0.0
    margin_used: float = 0.0
    margin_percent: float = 0.0
    open_positions_count: int = 0
    total_pnl: float = 0.0
    
    def to_dict(self):
        return asdict(self)