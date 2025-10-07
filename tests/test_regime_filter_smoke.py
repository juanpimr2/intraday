# tests/test_regime_filter_smoke.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

import types

# Importamos el motor y helpers de export
from backtesting.backtest_engine import BacktestEngine, export_results_to_csv, export_equity_to_csv, export_summary_to_json


def _make_intraday_df(start_utc: datetime, periods: int = 5, freq_minutes: int = 60):
    """
    Crea un DataFrame OHLCV mínimo con columnas esperadas por el motor:
      snapshotTime (UTC tz-aware), openPrice, highPrice, lowPrice, closePrice, volume
    """
    idx = [start_utc + timedelta(minutes=freq_minutes * i) for i in range(periods)]
    base = 100.0
    close = np.linspace(base, base * 1.01, periods)  # ligera tendencia alcista
    df = pd.DataFrame({
        "snapshotTime": pd.to_datetime(idx, utc=True),
        "openPrice": close - 0.1,
        "highPrice": close + 0.2,
        "lowPrice":  close - 0.2,
        "closePrice": close,
        "volume": 1000,
    })
    return df


def _patch_strategy_and_regime(monkeypatch, *, regime_label: str = "lateral", price_key="closePrice"):
    """
    Parchea:
      - backtesting.backtest_engine.detect_regime -> lista del mismo régimen para todas las barras
      - BacktestEngine.strategy.analyze -> señal BUY con confianza alta usando precio de cierre
    """
    import backtesting.backtest_engine as be

    def fake_detect_regime(df, atr_period=14, adx_threshold=25.0, atr_threshold_pct=0.5):
        # Devuelve una lista con la misma etiqueta de régimen que tenga el DataFrame
        return [regime_label] * len(df)

    monkeypatch.setattr(be, "detect_regime", fake_detect_regime, raising=True)

    # Parchear el objeto strategy de la instancia al vuelo
    def _install_fake_strategy(engine: BacktestEngine):
        class FakeStrategy:
            def analyze(self, subset_df: pd.DataFrame, epic: str):
                price = float(subset_df.iloc[-1][price_key])
                return {
                    "epic": epic,
                    "signal": "BUY",
                    "confidence": 0.99,
                    "current_price": price,
                }
        engine.strategy = FakeStrategy()

    return _install_fake_strategy


def test_regime_filter_blocks_lateral(monkeypatch, tmp_path):
    """
    Con REGIME_FILTER_ENABLED=True y bloqueo de 'lateral', no debería abrirse ninguna posición.
    """
    # Datos de un único día, 5 barras
    start = datetime(2025, 9, 1, 8, 0, tzinfo=timezone.utc)
    df = _make_intraday_df(start, periods=6, freq_minutes=60)
    data = {"EPIC.TEST": df}

    engine = BacktestEngine(initial_capital=10_000.0)
    # Debe estar activo por defecto según config, pero lo reforzamos:
    engine.regime_filter_enabled = True
    engine.regime_filter_block = "lateral"

    installer = _patch_strategy_and_regime(monkeypatch, regime_label="lateral")
    installer(engine)

    results = engine.run(historical_data=data)

    assert results.total_trades == 0, "No deberían existir trades cuando el régimen es 'lateral' y el filtro está activo"

    # Exports mínimos (para asegurar que no fallan sin trades)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    p1 = export_results_to_csv(results, filename="trades.csv", report_dir=run_dir)
    p2 = export_equity_to_csv(results, filename="equity.csv", report_dir=run_dir)
    p3 = export_summary_to_json(results, filename="metrics.json", report_dir=run_dir)
    assert p1.exists() and p2.exists() and p3.exists(), "Los archivos de export deberían generarse incluso sin trades"


def test_trending_allows_trades_and_sessions(monkeypatch):
    """
    Con régimen 'trending' debe permitir abrir y cerrar al menos un trade.
    Además, verificamos que se rellene la tabla por sesión si el cierre cae en ventana EU/US.
    """
    # Creamos 2 días. El segundo día forzará cierre final con END_OF_BACKTEST.
    start = datetime(2025, 9, 1, 6, 0, tzinfo=timezone.utc)  # 08:00 Europe/Madrid aprox. en CEST
    df_day1 = _make_intraday_df(start, periods=6, freq_minutes=60)  # 08:00..13:00 CET aproximado
    df_day2 = _make_intraday_df(start + timedelta(days=1), periods=6, freq_minutes=60)

    # Juntamos ambos días (simula 2 días de barras)
    df = pd.concat([df_day1, df_day2], ignore_index=True)
    data = {"EPIC.TEST": df}

    engine = BacktestEngine(initial_capital=10_000.0)
    engine.regime_filter_enabled = True
    engine.regime_filter_block = "lateral"

    installer = _patch_strategy_and_regime(monkeypatch, regime_label="trending")
    installer(engine)

    results = engine.run(historical_data=data)

    assert results.total_trades >= 1, "Debería existir al menos un trade con régimen 'trending'"

    # Debe existir equity.csv lógico (la función de export se probará indirectamente aquí)
    # Y comprobar que el análisis por sesión se calcula (puede estar vacío si las horas no caen en ventanas).
    # Al menos el dict debe existir:
    assert isinstance(results.performance_by_session, dict)

    # En muchos casos la última barra caerá en EU_OPEN (08:00–12:00 CET) o EU_PM (12:00–16:00)
    # No forzamos que haya una clave concreta, solo validamos estructura y tipos:
    for k, v in results.performance_by_session.items():
        assert {"total_trades", "win_rate", "profit_factor", "total_pnl", "avg_pnl"} <= set(v.keys()), \
            f"Estructura inesperada en sesión '{k}'"


def test_exports_roundtrip(monkeypatch, tmp_path):
    """
    Ejecuta un run pequeño 'trending' y verifica que los tres archivos de salida existan.
    """
    start = datetime(2025, 9, 1, 6, 0, tzinfo=timezone.utc)
    df = _make_intraday_df(start, periods=8, freq_minutes=60)
    data = {"EPIC.TEST": df}

    engine = BacktestEngine(initial_capital=10_000.0)
    installer = _patch_strategy_and_regime(monkeypatch, regime_label="trending")
    installer(engine)
    # Desactivamos el filtro para no depender del valor de Config
    engine.regime_filter_enabled = False

    results = engine.run(historical_data=data)

    run_dir = tmp_path / "reports_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    path_trades = export_results_to_csv(results, report_dir=run_dir)
    path_eq = export_equity_to_csv(results, report_dir=run_dir)
    path_json = export_summary_to_json(results, report_dir=run_dir)

    assert path_trades.exists()
    assert path_eq.exists()
    assert path_json.exists()

    # Cargar JSON y validar campos esenciales
    import json
    d = json.loads(path_json.read_text(encoding="utf-8"))
    for section in ("capital", "trades", "risk", "temporal"):
        assert section in d, f"Falta sección '{section}' en metrics.json"
