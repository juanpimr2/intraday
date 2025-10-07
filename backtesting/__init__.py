"""
backtesting package

Exporta únicamente el motor unificado y los helpers de exportación.
Elimina referencias al motor avanzado antiguo para evitar errores de import.

Uso:
    from backtesting import BacktestEngine, export_results_to_csv, export_summary_to_json
"""

from .backtest_engine import (
    BacktestEngine,
    export_results_to_csv,
    export_summary_to_json,
)

__all__ = [
    "BacktestEngine",
    "export_results_to_csv",
    "export_summary_to_json",
]
