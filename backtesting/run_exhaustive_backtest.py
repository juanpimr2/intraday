#!/usr/bin/env python3
"""
Script para ejecutar backtesting exhaustivo con 6+ meses de datos
Genera análisis completo con todas las métricas avanzadas
"""

import sys
import os
import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Añadir path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backtesting.advanced_backtest_engine import (
    AdvancedBacktestEngine, 
    export_results_to_csv,
    export_summary_to_json
)
from api.capital_client import CapitalClient
from config import Config
from utils.helpers import setup_console_encoding, safe_float

setup_console_encoding()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest_exhaustive.log', encoding='utf-8'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def fetch_historical_data_extended(
    api: CapitalClient,
    assets: list,
    months: int = 6,
    resolution: str = "HOUR"
) -> dict:
    """
    Obtiene datos históricos extendidos (múltiples llamadas a la API)
    
    Args:
        api: Cliente API
        assets: Lista de activos
        months: Meses de histórico deseados
        resolution: Resolución temporal
        
    Returns:
        Dict con DataFrames por activo
    """
    logger.info("="*80)
    logger.info(f"📥 DESCARGANDO DATOS HISTÓRICOS - {months} MESES")
    logger.info("="*80)
    
    historical_data = {}
    
    # Capital.com limita a ~1000 puntos por llamada
    # Para HOUR: 1000 horas ≈ 41 días
    # Para obtener 6 meses necesitamos ~4-5 llamadas
    
    points_per_call = 1000
    
    if resolution == "HOUR":
        hours_per_month = 24 * 30
        total_hours = months * hours_per_month
        calls_needed = (total_hours // points_per_call) + 1
        logger.info(f"📊 Resolución: {resolution}")
        logger.info(f"📅 Período objetivo: {months} meses (~{total_hours} horas)")
        logger.info(f"📞 Llamadas necesarias: {calls_needed} por activo")
    else:
        calls_needed = 1
        logger.info(f"📊 Resolución: {resolution}")
        logger.info(f"📞 Llamadas: 1 por activo")
    
    logger.info("-"*80)
    
    for asset in assets:
        logger.info(f"\n🔍 Descargando {asset}...")
        
        try:
            all_data = []
            
            for call_num in range(calls_needed):
                logger.info(f"   📞 Llamada {call_num + 1}/{calls_needed}...")
                
                data = api.get_market_data(
                    asset, 
                    resolution, 
                    max_values=points_per_call
                )
                
                if data and 'prices' in data and data['prices']:
                    df = pd.DataFrame(data['prices'])
                    
                    # Convertir precios
                    for col in ['closePrice', 'openPrice', 'highPrice', 'lowPrice']:
                        if col in df.columns:
                            df[col] = df[col].apply(lambda x: safe_float(x))
                    
                    df['closePrice'] = pd.to_numeric(df['closePrice'], errors='coerce')
                    df = df.dropna(subset=['closePrice'])
                    
                    if not df.empty:
                        all_data.append(df)
                        logger.info(f"   ✅ {len(df)} puntos obtenidos")
                else:
                    logger.warning(f"   ⚠️  Sin datos en llamada {call_num + 1}")
                    break
            
            # Combinar todos los datos
            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)
                
                # Eliminar duplicados si los hay
                if 'snapshotTime' in combined_df.columns:
                    combined_df = combined_df.drop_duplicates(subset=['snapshotTime'])
                    combined_df = combined_df.sort_values('snapshotTime')
                
                historical_data[asset] = combined_df
                
                # Calcular período real obtenido
                if 'snapshotTime' in combined_df.columns:
                    dates = pd.to_datetime(combined_df['snapshotTime'])
                    start_date = dates.min()
                    end_date = dates.max()
                    days = (end_date - start_date).days
                    
                    logger.info(f"   📊 Total puntos: {len(combined_df)}")
                    logger.info(f"   📅 Período: {start_date.date()} a {end_date.date()}")
                    logger.info(f"   📆 Días de datos: {days}")
                    logger.info(f"   ✅ {asset} completado")
                else:
                    logger.info(f"   ✅ {asset}: {len(combined_df)} puntos")
            else:
                logger.warning(f"   ⚠️  No se pudieron obtener datos para {asset}")
        
        except Exception as e:
            logger.error(f"   ❌ Error descargando {asset}: {e}")
    
    logger.info("\n" + "="*80)
    logger.info("📊 RESUMEN DE DESCARGA")
    logger.info("="*80)
    logger.info(f"Activos descargados: {len(historical_data)}/{len(assets)}")
    
    for asset, df in historical_data.items():
        logger.info(f"  {asset}: {len(df)} puntos")
    
    return historical_data


def save_historical_data(historical_data: dict, output_dir: str = "backtest_data"):
    """Guarda datos históricos en archivos CSV para reutilizar"""
    Path(output_dir).mkdir(exist_ok=True)
    
    logger.info(f"\n💾 Guardando datos históricos en {output_dir}/")
    
    for asset, df in historical_data.items():
        filename = f"{output_dir}/{asset}_historical.csv"
        df.to_csv(filename, index=False)
        logger.info(f"  ✅ {filename}")
    
    logger.info("💾 Datos guardados correctamente")


def load_historical_data(input_dir: str = "backtest_data") -> dict:
    """Carga datos históricos desde archivos CSV"""
    historical_data = {}
    
    if not Path(input_dir).exists():
        logger.warning(f"⚠️  Directorio {input_dir} no existe")
        return historical_data
    
    logger.info(f"\n📂 Cargando datos históricos desde {input_dir}/")
    
    for filepath in Path(input_dir).glob("*_historical.csv"):
        asset = filepath.stem.replace('_historical', '')
        
        try:
            df = pd.read_csv(filepath)
            
            # Asegurar tipos correctos
            for col in ['closePrice', 'openPrice', 'highPrice', 'lowPrice']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['closePrice'])
            
            if not df.empty:
                historical_data[asset] = df
                logger.info(f"  ✅ {asset}: {len(df)} puntos")
        
        except Exception as e:
            logger.error(f"  ❌ Error cargando {filepath}: {e}")
    
    return historical_data


def run_exhaustive_backtest(
    months: int = 6,
    initial_capital: float = 10000.0,
    use_cached_data: bool = True,
    save_data: bool = True
):
    """
    Ejecuta backtest exhaustivo completo
    
    Args:
        months: Meses de datos históricos
        initial_capital: Capital inicial
        use_cached_data: Usar datos guardados si existen
        save_data: Guardar datos descargados
    """
    logger.info("="*80)
    logger.info("🚀 BACKTESTING EXHAUSTIVO - INICIO")
    logger.info("="*80)
    logger.info(f"Configuración:")
    logger.info(f"  Capital inicial: €{initial_capital:,.2f}")
    logger.info(f"  Período: {months} meses")
    logger.info(f"  Activos: {', '.join(Config.ASSETS)}")
    logger.info(f"  Estrategia: {Config.SL_TP_MODE}")
    logger.info(f"  Stop Loss (BUY): {Config.STOP_LOSS_PERCENT_BUY*100:.1f}%")
    logger.info(f"  Take Profit (BUY): {Config.TAKE_PROFIT_PERCENT_BUY*100:.1f}%")
    logger.info("="*80)
    
    # 1. OBTENER DATOS HISTÓRICOS
    historical_data = {}
    
    if use_cached_data:
        logger.info("\n🔄 Intentando cargar datos guardados...")
        historical_data = load_historical_data()
    
    if not historical_data:
        logger.info("\n📡 Conectando a Capital.com API...")
        api = CapitalClient()
        
        if not api.authenticate():
            logger.error("❌ Error de autenticación")
            return None
        
        logger.info("✅ Autenticado correctamente")
        
        # Descargar datos
        historical_data = fetch_historical_data_extended(
            api,
            Config.ASSETS,
            months=months,
            resolution=Config.TIMEFRAME
        )
        
        # Guardar para futuro uso
        if save_data and historical_data:
            save_historical_data(historical_data)
        
        api.close_session()
    
    if not historical_data:
        logger.error("❌ No se pudieron obtener datos históricos")
        return None
    
    # 2. VALIDAR DATOS
    logger.info("\n🔍 Validando calidad de datos...")
    
    min_points_required = 720  # ~30 días con datos horarios
    valid_assets = []
    
    for asset, df in historical_data.items():
        if len(df) >= min_points_required:
            valid_assets.append(asset)
            logger.info(f"  ✅ {asset}: {len(df)} puntos (suficiente)")
        else:
            logger.warning(f"  ⚠️  {asset}: {len(df)} puntos (insuficiente, mín: {min_points_required})")
    
    if not valid_assets:
        logger.error("❌ Ningún activo tiene suficientes datos")
        return None
    
    # Filtrar solo activos válidos
    historical_data = {k: v for k, v in historical_data.items() if k in valid_assets}
    
    # 3. EJECUTAR BACKTEST
    logger.info("\n🔬 Ejecutando backtest exhaustivo...")
    logger.info("="*80)
    
    engine = AdvancedBacktestEngine(initial_capital=initial_capital)
    results = engine.run(historical_data)
    
    # 4. EXPORTAR RESULTADOS
    logger.info("\n💾 Exportando resultados...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # CSV con trades
    csv_filename = f"backtest_trades_{timestamp}.csv"
    export_results_to_csv(results, csv_filename)
    
    # JSON con resumen
    json_filename = f"backtest_summary_{timestamp}.json"
    export_summary_to_json(results, json_filename)
    
    # Equity curve
    if results.equity_curve:
        equity_df = pd.DataFrame(results.equity_curve)
        equity_filename = f"backtest_equity_{timestamp}.csv"
        equity_df.to_csv(equity_filename, index=False)
        logger.info(f"✅ Equity curve exportada a {equity_filename}")
    
    logger.info("\n" + "="*80)
    logger.info("✅ BACKTESTING EXHAUSTIVO COMPLETADO")
    logger.info("="*80)
    logger.info(f"📁 Archivos generados:")
    logger.info(f"  - {csv_filename}")
    logger.info(f"  - {json_filename}")
    logger.info(f"  - {equity_filename}")
    logger.info(f"  - backtest_exhaustive.log")
    logger.info("="*80)
    
    return results


def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Ejecuta backtesting exhaustivo con datos históricos extendidos'
    )
    
    parser.add_argument(
        '--months',
        type=int,
        default=6,
        help='Meses de datos históricos (default: 6)'
    )
    
    parser.add_argument(
        '--capital',
        type=float,
        default=10000.0,
        help='Capital inicial (default: 10000)'
    )
    
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='No usar datos guardados, descargar nuevos'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='No guardar datos descargados'
    )
    
    args = parser.parse_args()
    
    # Ejecutar backtest
    results = run_exhaustive_backtest(
        months=args.months,
        initial_capital=args.capital,
        use_cached_data=not args.no_cache,
        save_data=not args.no_save
    )
    
    if results:
        # Mostrar recomendación final
        print("\n" + "="*80)
        print("🎯 PRÓXIMOS PASOS RECOMENDADOS")
        print("="*80)
        
        if results.win_rate >= 50 and results.profit_factor >= 1.5 and results.max_drawdown <= 20:
            print("✅ La estrategia muestra resultados prometedores")
            print("")
            print("Recomendaciones:")
            print("  1. Ejecutar walk-forward optimization para validar robustez")
            print("  2. Probar con diferentes períodos (bull market vs bear market)")
            print("  3. Considerar pruebas en cuenta demo real por 1-2 meses")
            print("  4. Implementar el punto 3 de la lista: Reducir capital por trade a 2-5%")
        else:
            print("⚠️  La estrategia necesita optimización")
            print("")
            print("Problemas detectados:")
            
            if results.win_rate < 50:
                print("  ❌ Win rate bajo - Revisar criterios de entrada")
            
            if results.profit_factor < 1.5:
                print("  ❌ Profit factor insuficiente - Ajustar SL/TP")
            
            if results.max_drawdown > 20:
                print("  ❌ Drawdown excesivo - Reducir tamaño de posiciones")
            
            print("")
            print("Acciones sugeridas:")
            print("  1. Ajustar parámetros de indicadores")
            print("  2. Añadir filtros (ADX, ATR) para mejorar calidad de señales")
            print("  3. Implementar trailing stop loss")
            print("  4. Considerar diferentes SL/TP ratios")
        
        print("="*80)


if __name__ == "__main__":
    main()