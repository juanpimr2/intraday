"""
Indicadores técnicos para análisis de mercado
"""

import pandas as pd
import numpy as np
from typing import Tuple
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
    
    @staticmethod
    def atr(df: pd.DataFrame, period: int = None) -> float:
        """
        Calcula el ATR (Average True Range) - mide volatilidad
        
        Args:
            df: DataFrame con columnas highPrice, lowPrice, closePrice
            period: Período del ATR (default: Config.ATR_PERIOD)
            
        Returns:
            float: Valor actual del ATR
        """
        if period is None:
            period = Config.ATR_PERIOD
        
        try:
            high = pd.to_numeric(df['highPrice'], errors='coerce')
            low = pd.to_numeric(df['lowPrice'], errors='coerce')
            close = pd.to_numeric(df['closePrice'], errors='coerce')
            
            # True Range = max de:
            # 1. high - low
            # 2. abs(high - close_anterior)
            # 3. abs(low - close_anterior)
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            
            if not atr.empty and not pd.isna(atr.iloc[-1]):
                return float(atr.iloc[-1])
            return 0.0
        except Exception as e:
            return 0.0
    
    @staticmethod
    def atr_percent(df: pd.DataFrame, period: int = None) -> float:
        """
        Calcula ATR como porcentaje del precio (normalizado)
        Útil para comparar volatilidad entre diferentes activos
        
        Args:
            df: DataFrame con columnas highPrice, lowPrice, closePrice
            period: Período del ATR (default: Config.ATR_PERIOD)
            
        Returns:
            float: ATR como porcentaje del precio actual
        """
        atr_value = TechnicalIndicators.atr(df, period)
        
        try:
            current_price = float(df['closePrice'].iloc[-1])
            if current_price > 0:
                return (atr_value / current_price) * 100
        except:
            pass
        
        return 0.0
    
    @staticmethod
    def adx(df: pd.DataFrame, period: int = None) -> Tuple[float, float, float]:
        """
        Calcula ADX (Average Directional Index) - mide fuerza de tendencia
        También calcula +DI y -DI para determinar dirección
        
        Args:
            df: DataFrame con highPrice, lowPrice, closePrice
            period: Período del ADX (default: Config.ADX_PERIOD)
            
        Returns:
            tuple: (adx, plus_di, minus_di)
                - adx: Fuerza de la tendencia (0-100)
                - plus_di: Indicador direccional positivo
                - minus_di: Indicador direccional negativo
        """
        if period is None:
            period = Config.ADX_PERIOD
        
        try:
            high = pd.to_numeric(df['highPrice'], errors='coerce')
            low = pd.to_numeric(df['lowPrice'], errors='coerce')
            close = pd.to_numeric(df['closePrice'], errors='coerce')
            
            # Calcular +DM y -DM (movimientos direccionales)
            high_diff = high.diff()
            low_diff = -low.diff()
            
            plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
            minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
            
            # Calcular True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Suavizar con Wilder's smoothing (EMA con alpha = 1/period)
            atr = tr.ewm(alpha=1/period, adjust=False).mean()
            plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
            minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
            
            # Calcular DX (Directional Index)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            
            # Calcular ADX (suavizado del DX)
            adx = dx.ewm(alpha=1/period, adjust=False).mean()
            
            if not adx.empty and not pd.isna(adx.iloc[-1]):
                return (
                    float(adx.iloc[-1]),
                    float(plus_di.iloc[-1]),
                    float(minus_di.iloc[-1])
                )
            return 0.0, 0.0, 0.0
            
        except Exception as e:
            return 0.0, 0.0, 0.0