"""
utils/market_regime.py

Detector simple de régimen de mercado: trending vs lateral.

Método:
- Calcula ATR (Average True Range) y ADX (Average Directional Index) aproximado.
- Clasifica cada barra según umbrales configurables.
- Devuelve una serie con etiquetas: "trending" o "lateral".

Uso:
    from utils.market_regime import detect_regime
    regimes = detect_regime(df, atr_period=14, adx_threshold=25)
"""

from __future__ import annotations
import pandas as pd
import numpy as np


def detect_regime(
    df: pd.DataFrame,
    atr_period: int = 14,
    adx_threshold: float = 25.0,
    atr_threshold_pct: float = 0.5,
) -> pd.Series:
    """
    Clasifica el régimen de mercado para cada fila de df.

    Parámetros
    ----------
    df : pd.DataFrame
        Debe contener columnas: ['highPrice', 'lowPrice', 'closePrice']
    atr_period : int
        Ventana para ATR y ADX.
    adx_threshold : float
        Umbral ADX para considerar tendencia.
    atr_threshold_pct : float
        Porcentaje del ATR sobre el precio (en %) que define si hay volatilidad suficiente.

    Retorna
    -------
    pd.Series
        Serie con valores: "trending" o "lateral".
    """
    if not all(col in df.columns for col in ["highPrice", "lowPrice", "closePrice"]):
        raise ValueError("El DataFrame debe contener highPrice, lowPrice y closePrice.")

    high, low, close = df["highPrice"], df["lowPrice"], df["closePrice"]

    # --- ATR aproximado ---
    tr = np.maximum(high - low, np.maximum(abs(high - close.shift()), abs(low - close.shift())))
    atr = tr.rolling(atr_period).mean()

    # --- Direccionalidad (ADX simplificado) ---
    up_move = high - high.shift()
    down_move = low.shift() - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    plus_di = 100 * pd.Series(plus_dm).rolling(atr_period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(atr_period).mean() / atr
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(atr_period).mean()

    # --- Clasificación ---
    volatility = (atr / close) * 100
    trending_mask = (adx > adx_threshold) & (volatility > atr_threshold_pct)
    regimes = pd.Series(np.where(trending_mask, "trending", "lateral"), index=df.index)

    return regimes.fillna("lateral")
