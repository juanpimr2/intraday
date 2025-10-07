"""
tests/test_backtesting_metrics.py

Pruebas unitarias sobre métricas puras de backtesting.

Requisitos:
- Depende de `backtesting/metrics.py`.
- No toca producción ni el dashboard.

Cómo ejecutar solo este módulo:
    python -m pytest tests/test_backtesting_metrics.py -q
"""

import math
import numpy as np
import pandas as pd
import pytest

from backtesting.metrics import (
    win_rate,
    profit_factor,
    sharpe,
    max_drawdown,
    recovery_time,
    calmar,
)


def test_win_rate_basic():
    # 3 ganadores (100, 20, 30), 2 perdedores (-50, -10), 1 neutro (0 no cuenta)
    trades = [100, -50, 0, 20, -10, 30]
    assert win_rate(trades) == pytest.approx(0.6, rel=1e-12)


def test_profit_factor_basic():
    trades = [100, -50, 0, 20, -10, 30]
    # (100 + 20 + 30) / (50 + 10) = 150 / 60 = 2.5
    assert profit_factor(trades) == pytest.approx(2.5, rel=1e-12)


def test_profit_factor_edge_cases():
    # Sin pérdidas -> PF = inf
    trades_no_losses = [10, 0, 5]
    assert math.isinf(profit_factor(trades_no_losses))

    # Sin ganancias -> PF = 0.0
    trades_no_gains = [-3, 0, -7]
    assert profit_factor(trades_no_gains) == 0.0

    # Sin trades -> NaN
    assert math.isnan(profit_factor([]))


def test_sharpe_daily_against_manual():
    # Serie de retornos diarios con media y std conocidos
    # r = [0.01, -0.005, 0.002, 0.0, 0.003, -0.004, 0.006, -0.002, 0.0, 0.004]
    r = pd.Series([0.01, -0.005, 0.002, 0.0, 0.003, -0.004, 0.006, -0.002, 0.0, 0.004])
    # Manual (rf = 0): Sharpe_ann = mean/std * sqrt(252)
    mean = r.mean()
    std = r.std(ddof=1)
    expected = (mean / std) * np.sqrt(252)
    got = sharpe(r, risk_free=0.0, period="daily")
    assert got == pytest.approx(expected, rel=1e-12)


def test_max_drawdown_and_recovery_time():
    # Equity con un drawdown claro desde 107 hasta 101 y recuperación a 108
    equity = pd.Series([100, 105, 103, 107, 101, 102, 108, 107, 111])
    # MDD = 101/107 - 1 = -0.056074... => magnitud 0.056074...
    expected_mdd = abs(101 / 107 - 1.0)
    assert max_drawdown(equity) == pytest.approx(expected_mdd, rel=1e-12)

    # Recuperación: pico en idx=3 (107) recupera y supera en idx=6 (108) => 3 barras
    assert recovery_time(equity) == 3


def test_calmar_ratio():
    assert calmar(0.20, 0.10) == pytest.approx(2.0, rel=1e-12)
    # Max DD = 0 => inf
    assert math.isinf(calmar(0.10, 0.0))
    # Acepta DD negativo (lo convierte a magnitud)
    assert calmar(0.15, -0.05) == pytest.approx(3.0, rel=1e-12)


def test_win_rate_and_sharpe_robust_to_nans_infs():
    # Métricas deben ignorar NaN/Inf internamente
    trades = [1.0, float("nan"), float("inf"), -1.0, 0.0]
    # ganadores: [1.0] / decisivos: [1.0, -1.0] => 0.5
    assert win_rate(trades) == pytest.approx(0.5, rel=1e-12)

    rets = pd.Series([0.01, np.nan, np.inf, -0.005, 0.002])
    # Sharpe bien definido con datos válidos restantes
    got = sharpe(rets, risk_free=0.0, period="daily")
    assert not math.isnan(got)
