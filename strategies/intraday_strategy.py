"""
Estrategia de trading intraday
"""

import pandas as pd
import logging
from typing import Dict
from indicators.technical import TechnicalIndicators
from config import Config

logger = logging.getLogger(__name__)


class IntradayStrategy:
    """Estrategia de trading intraday basada en indicadores técnicos"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def analyze(self, df: pd.DataFrame, epic: str) -> Dict:
        """
        Analiza el mercado y genera señales de trading
        
        Args:
            df: DataFrame con datos de mercado (debe tener columna 'closePrice')
            epic: Identificador del activo
            
        Returns:
            Dict: {
                'epic': str,
                'signal': 'BUY'|'SELL'|'NEUTRAL',
                'confidence': float (0-1),
                'current_price': float,
                'reasons': list[str],
                'indicators': dict
            }
        """
        if df.empty or len(df) < Config.SMA_LONG:
            return self._neutral_signal(epic, 0.0)
        
        # Preparar serie de precios
        close_series = pd.Series(df['closePrice'].values)
        current_price = float(close_series.iloc[-1])
        
        # Calcular indicadores
        rsi = self.indicators.rsi(close_series)
        macd, macd_signal, macd_hist = self.indicators.macd(close_series)
        sma_short = self.indicators.sma(close_series, Config.SMA_SHORT)
        sma_long = self.indicators.sma(close_series, Config.SMA_LONG)
        momentum = self.indicators.momentum(close_series)
        
        # Evaluar señales
        buy_score = 0
        sell_score = 0
        reasons = []
        
        # 1. Análisis de tendencia (SMAs)
        golden_cross = sma_short > sma_long
        price_above_long = current_price > sma_long
        
        if golden_cross and price_above_long:
            buy_score += 2
            reasons.append("Tendencia alcista clara (Golden Cross)")
        elif not golden_cross and not price_above_long:
            sell_score += 2
            reasons.append("Tendencia bajista clara (Death Cross)")
        
        # 2. RSI
        if rsi < Config.RSI_OVERSOLD:
            buy_score += 2
            reasons.append(f"RSI en sobreventa ({rsi:.1f})")
        elif rsi > Config.RSI_OVERBOUGHT:
            sell_score += 2
            reasons.append(f"RSI en sobrecompra ({rsi:.1f})")
        
        # 3. MACD
        if macd > macd_signal and macd_hist > 0:
            buy_score += 2
            reasons.append("MACD alcista")
        elif macd < macd_signal and macd_hist < 0:
            sell_score += 2
            reasons.append("MACD bajista")
        
        # 4. Momentum
        if momentum > 2:
            buy_score += 1
            reasons.append(f"Momentum positivo ({momentum:.1f}%)")
        elif momentum < -2:
            sell_score += 1
            reasons.append(f"Momentum negativo ({momentum:.1f}%)")
        
        # 5. Posición del precio respecto a SMAs
        if current_price > sma_short and current_price > sma_long:
            buy_score += 1
            reasons.append("Precio sobre ambas medias móviles")
        elif current_price < sma_short and current_price < sma_long:
            sell_score += 1
            reasons.append("Precio bajo ambas medias móviles")
        
        # Determinar señal final
        if buy_score >= Config.MIN_SIGNALS_TO_TRADE and buy_score > sell_score:
            signal = 'BUY'
            confidence = min(buy_score / 7, 1.0)
        elif sell_score >= Config.MIN_SIGNALS_TO_TRADE and sell_score > buy_score:
            signal = 'SELL'
            confidence = min(sell_score / 7, 1.0)
        else:
            signal = 'NEUTRAL'
            confidence = 0.0
        
        return {
            'epic': epic,
            'signal': signal,
            'confidence': confidence,
            'current_price': current_price,
            'reasons': reasons,
            'indicators': {
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'macd_hist': macd_hist,
                'sma_short': sma_short,
                'sma_long': sma_long,
                'momentum': momentum
            }
        }
    
    def _neutral_signal(self, epic: str, price: float) -> Dict:
        """Retorna una señal neutral"""
        return {
            'epic': epic,
            'signal': 'NEUTRAL',
            'confidence': 0.0,
            'current_price': price,
            'reasons': [],
            'indicators': {}
        }