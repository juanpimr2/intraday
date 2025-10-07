"""
tests/test_backtest_engine_smoke.py

Prueba de humo ("smoke test") del motor de backtesting completo.
Verifica que:
- El backtest corre sin excepciones con un dataset mínimo.
- Se generan métricas básicas y un número válido de trades.
- Las curvas y resultados son coherentes (no NaN / no negativos irreales).

Cómo ejecutar:
    python -m pytest tests/test_backtest_engine_smoke.py -q
"""

import os
import pandas as pd
import pytest

from backtesting.backtest_engine import BacktestEngine


@pytest.fixture
def sample_data(tmp_path):
    """
    Genera dataset de ejemplo en memoria similar a CSV de fixture.
    """
    dates = pd.date_range("2024-01-15", "2024-01-20", freq="H")
    df = pd.DataFrame({
        "snapshotTime": dates,
        "openPrice":  [1.10 + 0.001*i for i in range(len(dates))],
        "highPrice":  [1.11 + 0.001*i for i in range(len(dates))],
        "lowPrice":   [1.09 + 0.001*i for i in range(len(dates))],
        "closePrice": [1.10 + 0.001*i for i in range(len(dates))],
        "volume":     [100 + i for i in range(len(dates))],
    })
    # Retorna dict como el motor espera
    return {"EURUSD": df.copy(), "GBPUSD": df.copy()}


def test_backtest_runs_and_generates_results(sample_data):
    """
    Smoke test: el motor debe correr y producir resultados coherentes.
    """
    engine = BacktestEngine(initial_capital=10000.0)
    results = engine.run(sample_data, start_date="2024-01-15", end_date="2024-01-20")

    # Verifica tipo y campos principales
    assert hasattr(results, "total_trades")
    assert results.total_trades >= 0
    assert isinstance(results.total_return, float)
    assert isinstance(results.win_rate, float)
    assert results.initial_capital == pytest.approx(10000.0)

    # Equity curve y métricas no vacías
    assert len(results.equity_curve) > 0
    assert all("equity" in e for e in results.equity_curve)
    assert not any(pd.isna(e["equity"]) for e in results.equity_curve)

    # Drawdown no negativo y coherente
    assert results.max_drawdown >= 0.0
    assert results.max_drawdown <= 100.0

    # Exportación simulada
    from backtesting.backtest_engine import export_results_to_csv, export_summary_to_json
    export_results_to_csv(results, "tests/tmp_smoke_trades.csv")
    export_summary_to_json(results, "tests/tmp_smoke_summary.json")

    assert os.path.exists("tests/tmp_smoke_trades.csv")
    assert os.path.exists("tests/tmp_smoke_summary.json")

    # Limpieza de archivos temporales
    os.remove("tests/tmp_smoke_trades.csv")
    os.remove("tests/tmp_smoke_summary.json")
