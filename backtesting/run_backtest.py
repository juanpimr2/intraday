#!/usr/bin/env python3
"""
backtesting/run_backtest.py

Runner simple para ejecutar un backtest rápido con el motor unificado.
- Soporta ejecución directa por ruta (python backtesting/run_backtest.py)
  y ejecución como módulo (python -m backtesting.run_backtest)
- Descarga datos vía API de Capital.com usando Config.ASSETS y Config.TIMEFRAME.
- Exporta trades a CSV y un resumen a JSON.

Sugerencia: para evitar problemas de imports, desde la raíz del repo:
    python -m backtesting.run_backtest
"""

from __future__ import annotations

import os
import sys
import logging
from typing import Dict, List

# ---------------------------------------------------------------------------
# HACK DE RUTA: permite ejecutar este archivo "por ruta" sin romper imports.
# Inserta la carpeta raíz del proyecto en sys.path.
# ---------------------------------------------------------------------------
THIS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

# Imports del proyecto (ya con PROJECT_ROOT en sys.path)
from backtesting.backtest_engine import (
    BacktestEngine,
    export_results_to_csv,
    export_summary_to_json,
)
from api.capital_client import CapitalClient
from config import Config
from utils.helpers import setup_console_encoding, safe_float

setup_console_encoding()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("backtest.log", encoding="utf-8"),
        logging.StreamHandler(stream=sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def fetch_historical_data(
    api: CapitalClient, assets: List[str], resolution: str = "HOUR", max_values: int = 1000
) -> Dict[str, pd.DataFrame]:
    """Descarga datos históricos de la API y los normaliza a DataFrame por activo."""
    historical_data: Dict[str, pd.DataFrame] = {}
    logger.info(f"📥 Descargando datos históricos de {len(assets)} activos...")

    for asset in assets:
        try:
            data = api.get_market_data(asset, resolution, max_values)
            if data and "prices" in data and data["prices"]:
                df = pd.DataFrame(data["prices"])

                # Convertir columnas numéricas conocidas
                for col in ["closePrice", "openPrice", "highPrice", "lowPrice"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col].apply(lambda x: safe_float(x)), errors="coerce")

                df = df.dropna(subset=["closePrice"])
                if not df.empty:
                    historical_data[asset] = df
                    logger.info(f"✅ {asset}: {len(df)} velas descargadas")
                else:
                    logger.warning(f"⚠️  {asset}: DataFrame vacío tras limpieza")
            else:
                logger.warning(f"⚠️  No hay datos para {asset}")
        except Exception as e:
            logger.error(f"❌ Error descargando {asset}: {e}")

    return historical_data


def main():
    """Ejecuta un backtest rápido con parámetros desde Config."""
    logger.info("=" * 60)
    logger.info("🔬 BACKTESTING SYSTEM")
    logger.info("=" * 60)

    # 1) Autenticación
    api = CapitalClient()
    if not api.authenticate():
        logger.error("❌ Error de autenticación")
        return

    # 2) Datos históricos (llamadas paginadas ~1000 puntos)
    historical_data = fetch_historical_data(
        api=api,
        assets=Config.ASSETS,
        resolution=Config.TIMEFRAME,
        max_values=1000,  # ~1000 horas ≈ 40 días para HOUR
    )

    if not historical_data:
        logger.error("❌ No se pudieron descargar datos históricos")
        try:
            api.close_session()
        finally:
            return

    # 3) Ejecutar backtest (motor unificado)
    engine = BacktestEngine(initial_capital=10000.0)
    results = engine.run(historical_data)

    # 4) Exportar resultados (CSV + JSON)
    export_results_to_csv(results, "backtest_results.csv")
    export_summary_to_json(results, "backtest_summary.json")

    # 5) Cerrar sesión API
    api.close_session()

    logger.info("✅ Backtest finalizado. Archivos: backtest_results.csv, backtest_summary.json")


if __name__ == "__main__":
    main()
