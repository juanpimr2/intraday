"""
Indicadores técnicos para análisis de mercado
"""

import pandas as pd
import numpy as np
from config import Config


class TechnicalIndicators:
    """Clase con indicadores técnicos"""
    
    @staticmethod
    def rsi(series: pd.Series, period: int = None) -> float:
        """
        Calcula el RSI (Relative Strength Index)
        
        Args:
            series: Serie de precios
            period: Período del RSI (default: Config.RSI_PERIOD)
            
        Returns:
            float: Valor del RSI
        """
        if period is None:
            period = Config.RSI_PERIOD
            
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(window=period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        if not rsi.empty and not pd.isna(rsi.iloc[-1]):
            return float(rsi.iloc[-1])
        return 50.0
    
    @staticmethod
    def macd(series: pd.Series, fast: int = None, slow: int = None, signal: int = None):
        """
        Calcula el MACD (Moving Average Convergence Divergence)
        
        Args:
            series: Serie de precios
            fast: Período rápido (default: Config.MACD_FAST)
            slow: Período lento (default: Config.MACD_SLOW)
            signal: Período de señal (default: Config.MACD_SIGNAL)
            
        Returns:
            tuple: (macd, signal, histogram)
        """
        if fast is None:
            fast = Config.MACD_FAST
        if slow is None:
            slow = Config.MACD_SLOW
        if signal is None:
            signal = Config.MACD_SIGNAL
            
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return (
            float(macd_line.iloc[-1]),
            float(signal_line.iloc[-1]),
            float(histogram.iloc[-1])
        )
    
    @staticmethod
    def sma(series: pd.Series, period: int) -> float:
        """
        Calcula la SMA (Simple Moving Average)
        
        Args:
            series: Serie de precios
            period: Período de la media
            
        Returns:
            float: Valor de la SMA
        """
        sma = series.rolling(window=period).mean()
        value = sma.iloc[-1]
        
        if not pd.isna(value):
            return float(value)
        return float(series.iloc[-1])
    
    @staticmethod
    def momentum(series: pd.Series, period: int = 10) -> float:
        """
        Calcula el momentum
        
        Args:
            series: Serie de precios
            period: Período del momentum
            
        Returns:
            float: Valor del momentum en porcentaje
        """
        if len(series) < period:
            return 0.0
            
        current = series.iloc[-1]
        previous = series.iloc[-period]
        
        return float((current - previous) / previous * 100)
    
    @staticmethod
    def ema(series: pd.Series, period: int) -> float:
        """
        Calcula la EMA (Exponential Moving Average)
        
        Args:
            series: Serie de precios
            period: Período de la media
            
        Returns:
            float: Valor de la EMA
        """
        ema = series.ewm(span=period, adjust=False).mean()
        value = ema.iloc[-1]
        
        if not pd.isna(value):
            return float(value)
        return float(series.iloc[-1])