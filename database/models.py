"""
Modelos de datos para la base de datos
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict
import json


@dataclass
class TradingSession:
    """Modelo para sesión de trading"""
    start_time: datetime
    initial_balance: float
    session_id: Optional[int] = None
    end_time: Optional[datetime] = None
    final_balance: Optional[float] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: Optional[float] = None
    status: str = 'RUNNING'
    config_snapshot: Optional[Dict] = None
    
    def to_dict(self):
        data = asdict(self)
        if data.get('config_snapshot'):
            data['config_snapshot'] = json.dumps(data['config_snapshot'])
        return data


@dataclass
class Trade:
    """Modelo para operación"""
    session_id: int
    epic: str
    direction: str
    entry_time: datetime
    entry_price: float
    position_size: float
    stop_loss: float
    take_profit: float
    margin_used: float
    
    signal_id: Optional[int] = None
    deal_reference: Optional[str] = None
    confidence: Optional[float] = None
    sl_tp_mode: Optional[str] = None
    atr_at_entry: Optional[float] = None
    
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    duration_minutes: Optional[int] = None
    
    status: str = 'OPEN'
    entry_reasons: List[str] = field(default_factory=list)
    entry_indicators: Optional[Dict] = None
    trade_id: Optional[int] = None
    
    def to_dict(self):
        data = asdict(self)
        if data.get('entry_indicators'):
            data['entry_indicators'] = json.dumps(data['entry_indicators'])
        return data


@dataclass
class MarketSignal:
    """Modelo para señal de mercado"""
    session_id: int
    epic: str
    signal: str
    confidence: float
    current_price: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    rsi: Optional[float] = None
    macd: Optional[float] = None
    atr_percent: Optional[float] = None
    adx: Optional[float] = None
    
    reasons: List[str] = field(default_factory=list)
    executed: bool = False
    trade_id: Optional[int] = None
    signal_id: Optional[int] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class AccountSnapshot:
    """Modelo para snapshot de cuenta"""
    session_id: int
    balance: float
    available: float
    margin_used: float
    margin_percent: float
    timestamp: datetime = field(default_factory=datetime.now)
    open_positions_count: int = 0
    equity: Optional[float] = None
    snapshot_id: Optional[int] = None
    
    def to_dict(self):
        return asdict(self)
