"""
backtesting/metrics.py

Métricas puras para evaluar resultados de backtesting.
No introduce dependencias de producción y puede importarse desde tests u otros módulos.

Funciones expuestas:
- win_rate(trade_returns)
- profit_factor(trade_returns)
- sharpe(returns, risk_free=0.0, period='daily', periods_per_year=None)
- max_drawdown(equity)
- recovery_time(equity)
- calmar(annual_return, max_dd)

Notas de uso:
- `trade_returns` puede ser un iterable/array/Series de P&L por trade (en unidades monetarias) o retorno por trade (en %).
  Estas funciones no asumen tamaño de posición; sólo operan con el signo y suma de ganancias/pérdidas.
- `returns` debe ser una Serie/array de retornos simples por periodo (p.ej., r_t = (P_t / P_{t-1}) - 1).
- `equity` debe ser la curva de capital (valor acumulado) por barra/período.
"""

from __future__ import annotations

from typing import Iterable, Optional, Union
import numpy as np
import pandas as pd

Number = Union[int, float, np.number]
ArrayLike = Union[Iterable[Number], np.ndarray, pd.Series]


__all__ = [
    "win_rate",
    "profit_factor",
    "sharpe",
    "max_drawdown",
    "recovery_time",
    "calmar",
]


def _to_series(x: ArrayLike, name: str) -> pd.Series:
    """Convierte entrada a pd.Series y elimina NaNs/Inf."""
    if isinstance(x, pd.Series):
        s = x.copy()
    else:
        s = pd.Series(list(x), dtype=float, name=name)
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    return s


def win_rate(trade_returns: ArrayLike) -> float:
    """
    Calcula el porcentaje de trades ganadores.

    Parámetros
    ----------
    trade_returns : ArrayLike
        Serie/array de P&L o retornos por trade.

    Retorna
    -------
    float
        Proporción en [0, 1]. Devuelve np.nan si no hay trades válidos.

    Notas
    -----
    - Los trades con P&L exactamente 0 no cuentan ni como ganadores ni como perdedores.
    """
    s = _to_series(trade_returns, "trade_returns")
    if s.empty:
        return float("nan")
    denom = (s != 0).sum()
    if denom == 0:
        return 0.0
    wins = (s > 0).sum()
    return wins / denom


def profit_factor(trade_returns: ArrayLike) -> float:
    """
    Calcula el Profit Factor: suma de ganancias / suma absoluta de pérdidas.

    Parámetros
    ----------
    trade_returns : ArrayLike
        Serie/array de P&L o retornos por trade.

    Retorna
    -------
    float
        Profit Factor. Si no hay pérdidas, retorna np.inf.
        Si no hay ganancias, retorna 0.0. Si no hay trades, np.nan.
    """
    s = _to_series(trade_returns, "trade_returns")
    if s.empty:
        return float("nan")
    gross_profit = s[s > 0].sum()
    gross_loss = -s[s < 0].sum()  # valor positivo
    if gross_loss == 0 and gross_profit == 0:
        return 0.0
    if gross_loss == 0:
        return float("inf")
    if gross_profit == 0:
        return 0.0
    return gross_profit / gross_loss


def _annualization_factor(period: str, periods_per_year: Optional[int]) -> int:
    """
    Obtiene el factor de anualización.

    Si `periods_per_year` se especifica, tiene prioridad.
    En caso contrario, se usa `period` con mapeo estándar.
    """
    if periods_per_year is not None:
        if periods_per_year <= 0:
            raise ValueError("periods_per_year debe ser > 0")
        return int(periods_per_year)

    period = (period or "").lower()
    mapping = {
        "daily": 252,
        "weekly": 52,
        "monthly": 12,
        "hourly": 252 * 24,      # aprox. si el mercado está 24/5 ajusta según tus horas
        "15m": 252 * 26,         # ~6.5h * 4 = 26 barras de 15m en un día bursátil típico
        "15min": 252 * 26,
        "15-min": 252 * 26,
        "30m": 252 * 13,
        "30min": 252 * 13,
        "1m": int(252 * 6.5 * 60),    # 390 barras/min por día bursátil aprox.
        "minute": 252 * 390,
        "bar": 252,              # fallback conservador
        "": 252,
    }
    return int(mapping.get(period, 252))


def sharpe(
    returns: ArrayLike,
    risk_free: float = 0.0,
    period: str = "daily",
    periods_per_year: Optional[int] = None,
) -> float:
    """
    Calcula el Sharpe Ratio anualizado.

    Parámetros
    ----------
    returns : ArrayLike
        Serie/array de retornos simples por período (p.ej., r_t = P_t/P_{t-1} - 1).
    risk_free : float, opcional (default=0.0)
        Tasa libre de riesgo ANUAL en formato decimal (p.ej., 0.03 = 3%).
        Se des-anualiza internamente al período de `returns`.
    period : str, opcional (default='daily')
        Frecuencia de los retornos; usado para anualizar si `periods_per_year` es None.
    periods_per_year : int, opcional
        Si se proporciona, anula `period` y se usa directamente para anualizar.

    Retorna
    -------
    float
        Sharpe anualizado. Devuelve np.nan si la desviación estándar muestral es 0
        o no hay datos válidos.

    Notas
    -----
    - El cálculo usa desviación estándar muestral (ddof=1).
    - Los NaN/inf son ignorados.
    """
    r = _to_series(returns, "returns")
    if r.empty:
        return float("nan")

    n = _annualization_factor(period, periods_per_year)

    if risk_free < -0.999999999:
        raise ValueError("risk_free anual no puede ser <= -100%")
    rf_per_period = (1.0 + float(risk_free)) ** (1.0 / n) - 1.0

    excess = r - rf_per_period
    mean = excess.mean()
    std = excess.std(ddof=1)

    if std == 0 or np.isnan(std):
        return float("nan")

    sharpe_period = mean / std
    return float(np.sqrt(n) * sharpe_period)


def max_drawdown(equity: ArrayLike) -> float:
    """
    Calcula el Máximo Drawdown (magnitud positiva en [0, 1] si equity está normalizada).

    Parámetros
    ----------
    equity : ArrayLike
        Serie/array de valores de la curva de capital (equity) por período.

    Retorna
    -------
    float
        Máximo drawdown como magnitud positiva. Devuelve 0.0 si la serie es monótonamente no decreciente
        o si hay menos de 2 puntos válidos.

    Notas
    -----
    - El drawdown en t es (equity_t / peak_t - 1). El MDD es el mínimo (más negativo) de esa serie,
      devuelto en magnitud positiva (abs).
    """
    eq = _to_series(equity, "equity")
    if eq.size < 2:
        return 0.0

    running_peak = eq.cummax()
    dd = (eq / running_peak) - 1.0
    mdd = dd.min()  # valor más negativo
    return float(abs(mdd))


def recovery_time(equity: ArrayLike) -> int:
    """
    Calcula el mayor tiempo de recuperación (en número de períodos/barras) tras un drawdown.

    Definición:
    - Para cada nuevo máximo (peak), mide cuánto tarda la serie de equity en volver a superar ese peak
      después del siguiente drawdown. Devuelve el máximo de estas duraciones en número de barras.

    Parámetros
    ----------
    equity : ArrayLike
        Serie/array de la curva de capital.

    Retorna
    -------
    int
        Máximo tiempo de recuperación en número de períodos. 0 si nunca hay recuperaciones necesarias
        (serie no decreciente) o si no hay suficientes datos.

    Notas
    -----
    - Si el índice es temporal, puedes convertir el número de períodos a duración multiplicando por el
      delta medio entre barras en tu motor.
    """
    eq = _to_series(equity, "equity")
    n = len(eq)
    if n < 2:
        return 0

    running_peak = eq.cummax()
    peak_value_to_last_index = {}

    max_recovery = 0

    last_peak_val = None
    last_peak_idx = None

    for i in range(n):
        current = eq.iat[i]
        if current >= (running_peak.iat[i] - 1e-12):
            last_peak_val = running_peak.iat[i]
            last_peak_idx = i
            peak_value_to_last_index[last_peak_val] = i

        if i > 0 and running_peak.iat[i] > running_peak.iat[i - 1] + 1e-12:
            prev_peak_val = running_peak.iat[i - 1]
            prev_peak_idx = peak_value_to_last_index.get(prev_peak_val, None)
            if prev_peak_idx is not None:
                recovery = i - prev_peak_idx
                if recovery > max_recovery:
                    max_recovery = recovery

    return int(max_recovery)


def calmar(annual_return: float, max_dd: float) -> float:
    """
    Calcula el Calmar Ratio.

    Parámetros
    ----------
    annual_return : float
        Retorno anualizado (decimal). Ej.: 0.20 para 20%.
    max_dd : float
        Máximo drawdown en magnitud positiva (decimal). Ej.: 0.25 para -25%.

    Retorna
    -------
    float
        Calmar = annual_return / max_dd. Si max_dd == 0, retorna np.inf.

    Notas
    -----
    - Asegúrate de que `annual_return` esté calculado de manera consistente con tus retornos (p.ej., CAGR).
    """
    if max_dd < 0:
        max_dd = abs(max_dd)
    if max_dd == 0:
        return float("inf")
    return float(annual_return / max_dd)


# ==========================
# Ejemplos mínimos (doctest)
# ==========================
if __name__ == "__main__":
    trades = [100, -50, 0, 20, -10, 30]  # P&L
    print("Win rate:", win_rate(trades))                 # 0.6
    print("Profit factor:", profit_factor(trades))       # 2.5

    rng = pd.date_range("2024-01-01", periods=10, freq="B")
    rets = pd.Series([0.01, -0.005, 0.002, 0.0, 0.003, -0.004, 0.006, -0.002, 0.0, 0.004], index=rng)
    print("Sharpe (daily, rf=0):", sharpe(rets, risk_free=0.0, period="daily"))

    equity = pd.Series([100, 105, 103, 107, 101, 102, 108, 107, 111])
    print("Max DD:", max_drawdown(equity))               # ~0.05607
    print("Recovery bars:", recovery_time(equity))       # 3
    print("Calmar:", calmar(0.2, 0.1))                   # 2.0
