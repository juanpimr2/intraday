#!/usr/bin/env python3
"""
Script para ejecutar backtests
"""

import sys
import pandas as pd
import logging
from backtesting.backtest_engine import BacktestEngine, export_results_to_csv
from api.capital_client import CapitalClient
from config import Config
from utils.helpers import setup_console_encoding, safe_float

setup_console_encoding()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest.log', encoding='utf-8'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def fetch_historical_data(api: CapitalClient, assets: list, resolution: str = "HOUR", max_values: int = 1000) -> dict:
    """Obtiene datos históricos de la API"""
    historical_data = {}
    
    logger.info(f"📥 Descargando datos históricos de {len(assets)} activos...")
    
    for asset in assets:
        try:
            data = api.get_market_data(asset, resolution, max_values)
            
            if data and 'prices' in data and data['prices']:
                df = pd.DataFrame(data['prices'])
                
                # Convertir precios
                for col in ['closePrice', 'openPrice', 'highPrice', 'lowPrice']:
                    if col in df.columns:
                        df[col] = df[col].apply(lambda x: safe_float(x))
                
                df['closePrice'] = pd.to_numeric(df['closePrice'], errors='coerce')
                df = df.dropna(subset=['closePrice'])
                
                if not df.empty:
                    historical_data[asset] = df
                    logger.info(f"✅ {asset}: {len(df)} velas descargadas")
            else:
                logger.warning(f"⚠️  No hay datos para {asset}")
                
        except Exception as e:
            logger.error(f"❌ Error descargando {asset}: {e}")
    
    return historical_data


def main():
    """Función principal"""
    logger.info("="*60)
    logger.info("🔬 BACKTESTING SYSTEM")
    logger.info("="*60)
    
    # Autenticar con API
    api = CapitalClient()
    if not api.authenticate():
        logger.error("❌ Error de autenticación")
        return
    
    # Descargar datos históricos
    historical_data = fetch_historical_data(
        api,
        Config.ASSETS,
        resolution=Config.TIMEFRAME,
        max_values=1000  # ~1000 horas ≈ 40 días
    )
    
    if not historical_data:
        logger.error("❌ No se pudieron descargar datos históricos")
        return
    
    # Ejecutar backtest
    engine = BacktestEngine(initial_capital=10000.0)
    results = engine.run(historical_data)
    
    # Exportar resultados
    export_results_to_csv(results, 'backtest_results.csv')
    
    # Cerrar sesión API
    api.close_session()


if __name__ == "__main__":
    main()