"""
Bot de trading intraday con mejoras de ATR, ADX y MTF
Versión 6.1 - Octubre 2025
"""

import logging
import time
import pandas as pd
from datetime import datetime, time as dt_time
from typing import List, Dict, Optional

from api.capital_client import CapitalClient
from strategies.intraday_strategy import IntradayStrategy
from trading.position_manager import PositionManager
from utils.helpers import safe_float
from config import Config

logger = logging.getLogger(__name__)


class TradingBot:
    """Bot de trading automatizado con análisis técnico avanzado"""
    
    def __init__(self):
        """Inicializa el bot con sus componentes"""
        self.api = CapitalClient()
        self.strategy = IntradayStrategy()
        self.position_manager = PositionManager(self.api)
        self.account_info = {}
        self.is_running = False
    
    def run(self):
        """
        Inicia el bot de trading
        Loop principal que:
        1. Autentica con la API
        2. Obtiene info de cuenta
        3. Escanea mercados cada X segundos
        4. Ejecuta operaciones cuando hay señales válidas
        """
        logger.info("="*60)
        logger.info("🤖 BOT INTRADAY TRADING - Modo Modular v6.1")
        logger.info("="*60)
        logger.info(f"📊 Activos: {', '.join(Config.ASSETS)}")
        logger.info(f"⏰ Horario: {Config.START_HOUR}:00 - {Config.END_HOUR}:00")
        logger.info(f"🔄 Escaneo cada: {Config.SCAN_INTERVAL}s")
        logger.info(f"📈 Modo SL/TP: {Config.SL_TP_MODE}")
        logger.info(f"🎯 Filtro ADX: {'✅ Activo' if Config.ENABLE_ADX_FILTER else '❌ Desactivado'}")
        logger.info(f"🕒 MTF: {'✅ Activo' if Config.ENABLE_MTF else '❌ Desactivado'}")
        logger.info("="*60)
        
        self.is_running = True
        
        # Autenticar
        if not self.api.authenticate():
            logger.error("❌ Autenticación fallida. Revisa credenciales en config.py")
            return
        
        logger.info("✅ Autenticación exitosa")
        
        # Obtener info inicial de cuenta
        self.account_info = self.api.get_account_info()
        self._log_account_status()
        
        # Loop principal
        try:
            while self.is_running:
                # Verificar horario de trading
                if not self.is_trading_hours():
                    logger.info("⏸️  Fuera de horario de trading. Esperando...")
                    time.sleep(300)  # Esperar 5 minutos
                    continue
                
                # Actualizar info de cuenta
                self.account_info = self.api.get_account_info()
                
                # Escanear y operar
                self.scan_and_trade()
                
                # Esperar hasta el próximo escaneo
                logger.info(f"⏳ Próximo escaneo en {Config.SCAN_INTERVAL}s...\n")
                time.sleep(Config.SCAN_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("\n⚠️  Interrupción manual detectada")
            self.stop()
        except Exception as e:
            logger.error(f"❌ Error crítico en loop principal: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.stop()
    
    def scan_and_trade(self):
        """
        Escanea mercados y ejecuta operaciones
        
        Flujo:
        1. Analiza todos los activos configurados
        2. Filtra señales válidas (confianza > MIN_CONFIDENCE)
        3. Calcula sizing basado en margen disponible
        4. Planifica trades respetando límites de riesgo
        5. Ejecuta las operaciones
        """
        logger.info("="*60)
        logger.info("🔍 ESCANEANDO MERCADOS")
        logger.info("="*60)
        
        # Obtener señales de los mercados
        analyses = self._analyze_markets()
        
        if not analyses:
            logger.info("📊 No hay señales válidas en este momento")
            logger.info("="*60)
            return
        
        logger.info(f"\n💡 SEÑALES DETECTADAS: {len(analyses)}")
        
        # Filtrar por confianza mínima
        valid_signals = [
            a for a in analyses 
            if a['confidence'] >= Config.MIN_CONFIDENCE
        ]
        
        if not valid_signals:
            logger.info(f"⚠️  Todas las señales tienen confianza < {Config.MIN_CONFIDENCE:.0%}")
            logger.info("="*60)
            return
        
        logger.info(f"✅ Señales con confianza ≥ {Config.MIN_CONFIDENCE:.0%}: {len(valid_signals)}")
        
        # Calcular margen disponible y límites
        balance, available = self.position_manager.get_account_balance(self.account_info)
        margin_used = self.position_manager.calculate_margin_used(self.account_info)
        
        # Verificar posiciones actuales
        current_positions = self.position_manager.get_positions()
        
        if len(current_positions) >= Config.MAX_POSITIONS:
            logger.warning(f"⛔ Máximo de posiciones alcanzado ({Config.MAX_POSITIONS})")
            logger.info("="*60)
            return
        
        # Calcular cuánto margen podemos usar
        target_total_margin = available * Config.TARGET_PERCENT_OF_AVAILABLE
        total_limit = balance * Config.MAX_CAPITAL_RISK
        
        # Ajustar si ya tenemos margen usado
        available_for_new = min(target_total_margin, total_limit - margin_used)
        
        if available_for_new <= 0:
            logger.warning("⚠️  No hay margen disponible para nuevas operaciones")
            logger.info("="*60)
            return
        
        # Calcular margen por operación
        slots_available = Config.MAX_POSITIONS - len(current_positions)
        num_trades = min(len(valid_signals), slots_available)
        per_trade_margin = available_for_new / num_trades if num_trades > 0 else 0
        
        logger.info(f"\n💰 GESTIÓN DE CAPITAL:")
        logger.info(f"   Balance: €{balance:.2f} | Disponible: €{available:.2f}")
        logger.info(f"   Margen usado: €{margin_used:.2f}")
        logger.info(f"   Posiciones actuales: {len(current_positions)}/{Config.MAX_POSITIONS}")
        logger.info(f"   Margen objetivo por operación: €{per_trade_margin:.2f}")
        
        # Planificar trades
        plans = self._plan_trades(valid_signals, per_trade_margin, balance)
        
        if not plans:
            logger.info("⚠️  No se pudieron planificar trades (límites de riesgo)")
            logger.info("="*60)
            return
        
        # Ejecutar trades
        self._execute_trades(plans, margin_used, total_limit)
    
    def _analyze_markets(self) -> List[Dict]:
        """
        Analiza todos los mercados configurados
        Soporta análisis con múltiples timeframes (MTF) si está habilitado
        
        Returns:
            Lista de análisis con señales válidas (BUY/SELL)
        """
        analyses = []
        
        for epic in Config.ASSETS:
            try:
                if Config.ENABLE_MTF:
                    # MODO MTF: Analizar con múltiples timeframes
                    
                    # Timeframe rápido (señales de entrada)
                    market_data_fast = self.api.get_market_data(
                        epic, 
                        Config.TIMEFRAME_FAST,
                        max_values=200
                    )
                    
                    # Timeframe lento (filtro de tendencia)
                    market_data_slow = self.api.get_market_data(
                        epic, 
                        Config.TIMEFRAME_SLOW,
                        max_values=100
                    )
                    
                    if not market_data_fast or not market_data_slow:
                        logger.warning(f"⚠️  {epic}: Datos incompletos para MTF")
                        continue
                    
                    # Convertir a DataFrames
                    df_fast = self._convert_to_dataframe(market_data_fast)
                    df_slow = self._convert_to_dataframe(market_data_slow)
                    
                    if df_fast.empty or df_slow.empty:
                        logger.warning(f"⚠️  {epic}: DataFrames vacíos")
                        continue
                    
                    # Analizar con MTF
                    analysis = self.strategy.analyze_with_mtf(df_fast, df_slow, epic)
                    
                else:
                    # MODO SIMPLE: Un solo timeframe
                    market_data = self.api.get_market_data(
                        epic, 
                        Config.TIMEFRAME,
                        max_values=200
                    )
                    
                    if not market_data or 'prices' not in market_data:
                        logger.warning(f"⚠️  {epic}: No hay datos disponibles")
                        continue
                    
                    df = self._convert_to_dataframe(market_data)
                    
                    if df.empty:
                        logger.warning(f"⚠️  {epic}: DataFrame vacío")
                        continue
                    
                    # Analizar con timeframe único
                    analysis = self.strategy.analyze(df, epic)
                
                # Si hay señal válida, guardar
                if analysis['signal'] in ['BUY', 'SELL'] and analysis['current_price'] > 0:
                    analyses.append(analysis)
                    
                    # Log detallado
                    indicators = analysis.get('indicators', {})
                    logger.info(
                        f"📊 {epic}: {analysis['signal']} "
                        f"(conf {analysis['confidence']:.0%}) | "
                        f"Precio €{analysis['current_price']:.2f}"
                    )
                    logger.info(
                        f"   RSI {indicators.get('rsi', 0):.1f} | "
                        f"MACD {indicators.get('macd', 0):.4f} | "
                        f"ATR {analysis.get('atr_percent', 0):.2f}% | "
                        f"ADX {analysis.get('adx', 0):.1f}"
                        + (f" | MTF {analysis.get('slow_trend', 'N/A')}" if Config.ENABLE_MTF else "")
                    )
                    logger.info(f"   Razones: {', '.join(analysis['reasons'][:3])}")
                
                # Pequeña pausa entre requests
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"❌ Error analizando {epic}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        return analyses
    
    def _convert_to_dataframe(self, market_data: Dict) -> pd.DataFrame:
        """
        Convierte datos de mercado de la API a DataFrame limpio
        
        Args:
            market_data: Respuesta de la API con 'prices'
            
        Returns:
            DataFrame con precios limpios y validados
        """
        if not market_data or 'prices' not in market_data:
            return pd.DataFrame()
        
        try:
            df = pd.DataFrame(market_data['prices'])
            
            # Convertir precios a float
            for col in ['closePrice', 'openPrice', 'highPrice', 'lowPrice']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: safe_float(x))
            
            # Asegurar que closePrice es numérico y sin NaN
            df['closePrice'] = pd.to_numeric(df['closePrice'], errors='coerce')
            df = df.dropna(subset=['closePrice'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error convirtiendo datos a DataFrame: {e}")
            return pd.DataFrame()
    
    def _plan_trades(self, analyses: List[Dict], per_trade_margin: float, balance: float) -> List[Dict]:
        """
        Planifica las operaciones respetando límites de riesgo
        
        Args:
            analyses: Lista de análisis con señales válidas
            per_trade_margin: Margen objetivo por operación
            balance: Balance total de la cuenta
            
        Returns:
            Lista de planes de trading con todos los detalles
        """
        plans = []
        margin_by_asset = self.position_manager.get_margin_by_asset()
        asset_limit = balance * Config.MAX_MARGIN_PER_ASSET
        
        for analysis in analyses:
            epic = analysis['epic']
            price = safe_float(analysis['current_price'])
            direction = analysis['signal']
            atr_percent = analysis.get('atr_percent', 0)
            
            if price <= 0:
                logger.warning(f"⚠️  {epic}: Precio inválido ({price})")
                continue
            
            # Calcular tamaño de posición
            size, details, margin_est = self.position_manager.calculate_position_size(
                epic, price, per_trade_margin
            )
            
            # Verificar límite por activo
            asset_used = margin_by_asset.get(epic, 0.0)
            
            if asset_used + margin_est > asset_limit:
                logger.warning(
                    f"⛔ {epic}: Límite por activo excedido "
                    f"(actual €{asset_used:.2f} + nuevo €{margin_est:.2f} > límite €{asset_limit:.2f})"
                )
                continue
            
            # Calcular SL y TP (ahora con soporte dinámico basado en ATR)
            stop_loss = self.position_manager.calculate_stop_loss(
                price, 
                direction,
                atr_percent if Config.SL_TP_MODE == 'DYNAMIC' else None
            )
            
            take_profit = self.position_manager.calculate_take_profit(
                price, 
                direction,
                atr_percent if Config.SL_TP_MODE == 'DYNAMIC' else None
            )
            
            # Calcular ratio riesgo/beneficio
            rr_ratio = self.position_manager.get_risk_reward_ratio(
                price, stop_loss, take_profit, direction
            )
            
            # Filtrar trades con mal ratio R/R
            if rr_ratio < 1.0:
                logger.warning(
                    f"⛔ {epic}: Ratio R/R desfavorable ({rr_ratio:.2f} < 1.0). Trade rechazado."
                )
                continue
            
            # Agregar plan
            plans.append({
                'epic': epic,
                'direction': direction,
                'price': price,
                'size': size,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'margin_est': margin_est,
                'confidence': analysis['confidence'],
                'reasons': analysis['reasons'],
                'indicators': analysis['indicators'],
                'atr_percent': atr_percent,
                'adx': analysis.get('adx', 0),
                'rr_ratio': rr_ratio,
                'slow_trend': analysis.get('slow_trend')
            })
        
        return plans
    
    def _execute_trades(self, plans: List[Dict], margin_used: float, total_limit: float):
        """
        Ejecuta las operaciones planificadas
        
        Args:
            plans: Lista de planes de trading
            margin_used: Margen actualmente usado
            total_limit: Límite total de margen permitido
        """
        # Ordenar por confianza (ejecutar primero las de mayor confianza)
        plans.sort(key=lambda x: x['confidence'], reverse=True)
        
        executed = 0
        current_margin = margin_used
        
        logger.info("\n" + "="*60)
        logger.info(f"🚀 EJECUTANDO OPERACIONES ({len(plans)} planificadas)")
        logger.info("="*60)
        
        for i, plan in enumerate(plans, 1):
            # Verificar límite total antes de ejecutar
            new_total = current_margin + plan['margin_est']
            
            if new_total > total_limit:
                logger.warning(
                    f"⛔ Trade {i}/{len(plans)} saltado: Límite total excedido "
                    f"(nuevo total €{new_total:.2f} > límite €{total_limit:.2f})"
                )
                continue
            
            # Preparar orden
            order_data = {
                'epic': plan['epic'],
                'direction': plan['direction'],
                'size': plan['size'],
                'guaranteedStop': False,
                'stopLevel': plan['stop_loss'],
                'profitLevel': plan['take_profit']
            }
            
            # Log detallado de la orden
            logger.info("-"*60)
            logger.info(f"📤 ORDEN #{i}: {plan['direction']} {plan['epic']} @ €{plan['price']:.2f}")
            logger.info(f"   Tamaño: {plan['size']} | Margen: €{plan['margin_est']:.2f} | Confianza: {plan['confidence']:.0%}")
            logger.info(
                f"   SL: €{plan['stop_loss']:.2f} | "
                f"TP: €{plan['take_profit']:.2f} | "
                f"Ratio R/R: {plan['rr_ratio']:.2f}"
            )
            
            # Mostrar tipo de SL/TP usado
            if Config.SL_TP_MODE == 'DYNAMIC':
                logger.info(f"   💡 SL/TP Dinámico (ATR {plan['atr_percent']:.2f}%)")
            else:
                logger.info(f"   💡 SL/TP Estático (porcentajes fijos)")
            
            # Mostrar indicadores clave
            logger.info(
                f"   📊 ADX {plan['adx']:.1f} | "
                f"ATR {plan['atr_percent']:.2f}%"
                + (f" | MTF {plan.get('slow_trend', 'N/A')}" if Config.ENABLE_MTF else "")
            )
            
            # Mostrar top razones
            top_reasons = plan['reasons'][:3] if len(plan['reasons']) > 3 else plan['reasons']
            logger.info(f"   ✓ {', '.join(top_reasons)}")
            
            # Ejecutar orden
            try:
                result = self.api.place_order(order_data)
                
                if result:
                    deal_ref = result.get('dealReference', 'n/a')
                    logger.info(f"✅ Orden ejecutada exitosamente - Deal ID: {deal_ref}")
                    current_margin += plan['margin_est']
                    executed += 1
                else:
                    logger.error(f"❌ Error ejecutando orden (sin respuesta de API)")
                
            except Exception as e:
                logger.error(f"❌ Error ejecutando orden: {e}")
            
            # Pausa entre órdenes para no saturar API
            time.sleep(1)
        
        # Resumen final
        logger.info("="*60)
        logger.info(f"📊 RESUMEN DE EJECUCIÓN")
        logger.info("="*60)
        logger.info(f"   Órdenes ejecutadas: {executed}/{len(plans)}")
        logger.info(f"   Margen tras ejecuciones: €{current_margin:.2f}")
        logger.info(f"   Límite total: €{total_limit:.2f}")
        logger.info(f"   Utilización: {(current_margin/total_limit*100):.1f}%")
        logger.info("="*60)
    
    def is_trading_hours(self) -> bool:
        """
        Verifica si estamos en horario de trading
        
        Returns:
            True si es hora de operar, False si no
        """
        now = datetime.now()
        current_time = now.time()
        
        start = dt_time(Config.START_HOUR, 0)
        end = dt_time(Config.END_HOUR, 0)
        
        # Verificar si es fin de semana
        if now.weekday() >= 5:  # 5=Sábado, 6=Domingo
            return False
        
        return start <= current_time <= end
    
    def _log_account_status(self):
        """Log del estado de la cuenta"""
        balance, available = self.position_manager.get_account_balance(self.account_info)
        margin_used = self.position_manager.calculate_margin_used(self.account_info)
        
        logger.info("\n" + "="*60)
        logger.info("💰 ESTADO DE CUENTA")
        logger.info("="*60)
        logger.info(f"   Balance: €{balance:.2f}")
        logger.info(f"   Disponible: €{available:.2f}")
        logger.info(f"   Margen usado: €{margin_used:.2f}")
        logger.info(f"   % Utilización: {(margin_used/balance*100):.1f}%")
        logger.info("="*60)
    
    def stop(self):
        """Detiene el bot de forma ordenada"""
        logger.info("\n" + "="*60)
        logger.info("🛑 DETENIENDO BOT")
        logger.info("="*60)
        
        self.is_running = False
        
        # Mostrar estado final
        try:
            self.account_info = self.api.get_account_info()
            self._log_account_status()
            
            # Mostrar posiciones abiertas
            positions = self.position_manager.get_positions()
            if positions:
                logger.info(f"\n⚠️  Posiciones abiertas: {len(positions)}")
                for pos in positions:
                    pos_data = pos.get('position', {})
                    epic = pos_data.get('epic', 'Unknown')
                    direction = pos_data.get('direction', 'Unknown')
                    size = pos_data.get('size', 0)
                    logger.info(f"   - {epic}: {direction} {size}")
            else:
                logger.info("\n✅ No hay posiciones abiertas")
        except Exception as e:
            logger.error(f"Error obteniendo estado final: {e}")
        
        # Cerrar sesión de API
        try:
            self.api.close_session()
            logger.info("✅ Sesión de API cerrada")
        except Exception as e:
            logger.error(f"Error cerrando sesión: {e}")
        
        logger.info("="*60)
        logger.info("✅ Bot detenido correctamente")
        logger.info("="*60)


if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('intraday_trading_bot.log'),
            logging.StreamHandler()
        ]
    )
    
    # Crear y ejecutar bot
    bot = TradingBot()
    bot.run()