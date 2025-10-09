"""
Procesamiento y validación de señales de trading
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    """Representa una señal de trading"""
    epic: str
    direction: str  # 'BUY' o 'SELL'
    confidence: float
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    indicators: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def is_valid(self) -> bool:
        """Valida si la señal cumple criterios mínimos"""
        return (
            self.confidence >= 0.5 and
            self.stop_loss is not None and
            self.take_profit is not None
        )
    
    def risk_reward_ratio(self) -> float:
        """Calcula el ratio riesgo/beneficio"""
        if not self.stop_loss or not self.take_profit:
            return 0
        
        risk = abs(self.price - self.stop_loss)
        reward = abs(self.take_profit - self.price)
        
        return reward / risk if risk > 0 else 0


class SignalProcessor:
    """Procesa y filtra señales de trading"""
    
    def __init__(self, min_confidence: float = 0.5, min_signals: int = 2):
        self.min_confidence = min_confidence
        self.min_signals = min_signals
        self.signal_buffer = defaultdict(list)
        
    def process_indicators(self, epic: str, data: Dict[str, Any]) -> Optional[TradingSignal]:
        """Procesa indicadores y genera señal si corresponde"""
        
        signals = []
        confidence_scores = []
        
        # Evaluar RSI
        rsi_signal = self._evaluate_rsi(data.get('rsi'))
        if rsi_signal:
            signals.append(rsi_signal)
            confidence_scores.append(rsi_signal['confidence'])
        
        # Evaluar MACD
        macd_signal = self._evaluate_macd(data.get('macd'), data.get('macd_signal'))
        if macd_signal:
            signals.append(macd_signal)
            confidence_scores.append(macd_signal['confidence'])
        
        # Evaluar SMAs
        sma_signal = self._evaluate_smas(data.get('sma_short'), data.get('sma_long'))
        if sma_signal:
            signals.append(sma_signal)
            confidence_scores.append(sma_signal['confidence'])
        
        # Necesitamos mínimo N señales coincidentes
        if len(signals) < self.min_signals:
            return None
        
        # Verificar que todas las señales apuntan en la misma dirección
        directions = [s['direction'] for s in signals]
        if len(set(directions)) > 1:  # Señales contradictorias
            return None
        
        # Calcular confianza promedio
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        if avg_confidence < self.min_confidence:
            return None
        
        # Crear señal consolidada
        current_price = data.get('close', 0)
        direction = directions[0]
        
        # Calcular SL/TP
        sl, tp = self._calculate_sl_tp(current_price, direction, data.get('atr'))
        
        return TradingSignal(
            epic=epic,
            direction=direction,
            confidence=avg_confidence,
            price=current_price,
            stop_loss=sl,
            take_profit=tp,
            indicators={
                'rsi': data.get('rsi'),
                'macd': data.get('macd'),
                'sma_short': data.get('sma_short'),
                'sma_long': data.get('sma_long'),
                'signals_count': len(signals)
            }
        )
    
    def _evaluate_rsi(self, rsi: Optional[float]) -> Optional[Dict]:
        """Evalúa señal RSI"""
        if not rsi:
            return None
        
        if rsi < 35:  # Sobreventa
            return {'direction': 'BUY', 'confidence': 0.6, 'reason': f'RSI oversold ({rsi:.1f})'}
        elif rsi > 75:  # Sobrecompra
            return {'direction': 'SELL', 'confidence': 0.6, 'reason': f'RSI overbought ({rsi:.1f})'}
        
        return None
    
    def _evaluate_macd(self, macd: Optional[float], signal: Optional[float]) -> Optional[Dict]:
        """Evalúa señal MACD"""
        if macd is None or signal is None:
            return None
        
        # Cruce alcista
        if macd > signal and abs(macd - signal) > 0.001:
            return {'direction': 'BUY', 'confidence': 0.7, 'reason': 'MACD bullish cross'}
        # Cruce bajista
        elif macd < signal and abs(signal - macd) > 0.001:
            return {'direction': 'SELL', 'confidence': 0.7, 'reason': 'MACD bearish cross'}
        
        return None
    
    def _evaluate_smas(self, short: Optional[float], long: Optional[float]) -> Optional[Dict]:
        """Evalúa señal de medias móviles"""
        if not short or not long:
            return None
        
        # Golden cross
        if short > long * 1.001:  # 0.1% por encima
            return {'direction': 'BUY', 'confidence': 0.65, 'reason': 'Golden cross'}
        # Death cross
        elif short < long * 0.999:  # 0.1% por debajo
            return {'direction': 'SELL', 'confidence': 0.65, 'reason': 'Death cross'}
        
        return None
    
    def _calculate_sl_tp(self, price: float, direction: str, 
                        atr: Optional[float] = None) -> tuple:
        """Calcula Stop Loss y Take Profit"""
        # Usar ATR si está disponible, sino usar porcentajes fijos
        if atr and atr > 0:
            sl_distance = atr * 2.0
            tp_distance = atr * 3.0
        else:
            sl_distance = price * 0.08  # 8%
            tp_distance = price * 0.14  # 14%
        
        if direction == 'BUY':
            stop_loss = price - sl_distance
            take_profit = price + tp_distance
        else:  # SELL
            stop_loss = price + sl_distance
            take_profit = price - tp_distance
        
        return round(stop_loss, 2), round(take_profit, 2)