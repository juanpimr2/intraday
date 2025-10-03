"""
Bot de trading principal - Orquestador (Con control manual)
"""

import time
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict
from config import Config
from api.capital_client import CapitalClient
from strategies.intraday_strategy import IntradayStrategy
from trading.position_manager import PositionManager
from utils.helpers import safe_float
from utils.bot_controller import BotController

logger = logging.getLogger(__name__)


class TradingBot:
    """Bot de trading intraday - Orquestador principal"""
    
    def __init__(self):
        self.api = CapitalClient()
        self.strategy = IntradayStrategy()
        self.position_manager = PositionManager(self.api)
        self.controller = BotController()
        self.account_info = {}
        self.is_running = False
    
    def run(self):
        """Inicia el bot de trading"""
        logger.info("="*60)
        logger.info("BOT INTRADAY TRADING - Modo Modular v6.1")
        logger.info("Con control manual habilitado")
        logger.info("="*60)
        
        self.is_running = True
        
        # Autenticar
        if not self.api.authenticate():
            logger.error("❌ Autenticación fallida")
            return
        
        # Obtener info de cuenta inicial
        self.account_info = self.api.get_account_info()
        self._log_account_status()
        
        # Loop principal
        while self.is_running:
            try:
                # ✅ Verificar si el bot debe estar corriendo (control manual)
                if not self.controller.is_running():
                    logger.info("⏸️  Bot pausado manualmente. Esperando comando de inicio...")
                    time.sleep(10)  # Chequear cada 10 segundos
                    continue
                
                if not self.is_trading_hours():
                    logger.info("⏸️  Fuera de horario de trading")
                    time.sleep(300)  # 5 minutos
                    continue
                
                # Actualizar info de cuenta
                self.account_info = self.api.get_account_info()
                
                # Escanear y operar
                self.scan_and_trade()
                
                # Esperar hasta próximo escaneo
                logger.info(f"⏳ Próximo escaneo en {Config.SCAN_INTERVAL}s ({Config.SCAN_INTERVAL//60} min)...\n")
                time.sleep(Config.SCAN_INTERVAL)
                
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                logger.error(f"❌ Error en loop principal: {e}")
                time.sleep(300)  # Esperar 5 min antes de reintentar
    
    def scan_and_trade(self):
        """Escanea mercados y ejecuta operaciones"""
        logger.info("="*60)
        logger.info("🔍 ESCANEANDO MERCADOS")
        logger.info("="*60)
        
        if not self.account_info:
            logger.warning("⚠️  No hay información de cuenta disponible")
            return
        
        balance, available = self.position_manager.get_account_balance(self.account_info)
        
        if balance <= 0:
            logger.warning("⚠️  Balance insuficiente")
            return
        
        # Calcular límites
        margin_used = self.position_manager.calculate_margin_used(self.account_info)
        total_limit = balance * Config.MAX_CAPITAL_RISK
        remaining_margin = max(total_limit - margin_used, 0.0)
        
        self._log_margin_status(margin_used, total_limit, available, balance)
        
        if remaining_margin <= 0:
            logger.warning("⛔ Sin margen disponible para nuevas operaciones")
            return
        
        # Analizar mercados
        analyses = self._analyze_markets()
        
        if not analyses:
            logger.info("ℹ️  No hay oportunidades de trading válidas")
            return
        
        # Filtrar y ordenar por confianza
        analyses = [a for a in analyses if a['confidence'] >= Config.MIN_CONFIDENCE]
        analyses.sort(key=lambda x: x['confidence'], reverse=True)
        analyses = analyses[:Config.MAX_POSITIONS]
        
        # Calcular margen por operación
        total_target_margin = min(available * Config.TARGET_PERCENT_OF_AVAILABLE, remaining_margin)
        num_trades = len(analyses)
        per_trade_margin = total_target_margin / max(num_trades, 1)
        
        logger.info(f"💰 Margen TOTAL objetivo: €{total_target_margin:.2f} ({Config.TARGET_PERCENT_OF_AVAILABLE*100:.0f}% del disponible)")
        logger.info(f"🎯 Margen por operación: €{per_trade_margin:.2f} (dividido entre {num_trades} operaciones)")
        
        # Planificar operaciones
        plans = self._plan_trades(analyses, per_trade_margin, balance)
        
        if not plans:
            logger.info("ℹ️  No hay operaciones viables tras aplicar límites")
            return
        
        # Ejecutar operaciones
        self._execute_trades(plans, margin_used, total_limit)
    
    def _analyze_markets(self) -> List[Dict]:
        """Analiza todos los mercados del universo"""
        analyses = []
        
        for epic in Config.ASSETS:
            try:
                # Obtener datos de mercado
                market_data = self.api.get_market_data(epic, Config.TIMEFRAME)
                
                if not market_data or 'prices' not in market_data or not market_data['prices']:
                    logger.warning(f"⚠️  No hay datos para {epic}")
                    continue
                
                # Convertir a DataFrame
                df = pd.DataFrame(market_data['prices'])
                
                # Convertir precios
                for col in ['closePrice', 'openPrice', 'highPrice', 'lowPrice']:
                    if col in df.columns:
                        df[col] = df[col].apply(lambda x: safe_float(x))
                
                df['closePrice'] = pd.to_numeric(df['closePrice'], errors='coerce')
                df = df.dropna(subset=['closePrice'])
                
                if df.empty:
                    continue
                
                # Analizar con la estrategia
                analysis = self.strategy.analyze(df, epic)
                
                if analysis['signal'] in ['BUY', 'SELL'] and analysis['current_price'] > 0:
                    analyses.append(analysis)
                    logger.info(
                        f"📊 {epic}: {analysis['signal']} "
                        f"(conf {analysis['confidence']:.0%}) "
                        f"RSI {analysis['indicators']['rsi']:.1f}"
                    )
                
                time.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error analizando {epic}: {e}")
                continue
        
        return analyses
    
    def _plan_trades(self, analyses: List[Dict], per_trade_margin: float, balance: float) -> List[Dict]:
        """Planifica las operaciones a ejecutar"""
        plans = []
        margin_by_asset = self.position_manager.get_margin_by_asset()
        asset_limit = balance * Config.MAX_MARGIN_PER_ASSET
        
        logger.info(f"📋 Planificando operaciones:")
        logger.info(f"   Margen por operación objetivo: €{per_trade_margin:.2f}")
        logger.info(f"   Límite por activo: €{asset_limit:.2f} ({Config.MAX_MARGIN_PER_ASSET*100:.0f}% del balance)")
        
        for analysis in analyses:
            epic = analysis['epic']
            price = safe_float(analysis['current_price'])
            direction = analysis['signal']
            atr_pct = analysis.get('atr_percent', 0)
            
            logger.info(f"\n🔍 Analizando {epic}:")
            logger.info(f"   Precio: €{price:.2f}")
            logger.info(f"   Dirección: {direction}")
            logger.info(f"   ATR: {atr_pct:.2f}%")
            
            # Calcular tamaño de posición
            size, details, margin_est = self.position_manager.calculate_position_size(
                epic, price, per_trade_margin
            )
            
            logger.info(f"   Size calculado: {size}")
            logger.info(f"   Margen estimado: €{margin_est:.2f}")
            
            # Verificar límite por activo
            asset_used = margin_by_asset.get(epic, 0.0)
            total_margin_for_asset = asset_used + margin_est
            
            logger.info(f"   Margen ya usado en {epic}: €{asset_used:.2f}")
            logger.info(f"   Total si se ejecuta: €{total_margin_for_asset:.2f}")
            
            if total_margin_for_asset > asset_limit:
                logger.warning(
                    f"   ⛔ RECHAZADA: Límite por activo excedido "
                    f"(€{total_margin_for_asset:.2f} > €{asset_limit:.2f})"
                )
                continue
            
            # ✅ VERIFICACIÓN ADICIONAL: Margen estimado no debe exceder el objetivo en más de 2x
            if margin_est > per_trade_margin * 2.0:
                logger.warning(
                    f"   ⛔ RECHAZADA: Margen estimado (€{margin_est:.2f}) es más del doble "
                    f"del objetivo (€{per_trade_margin:.2f})"
                )
                continue
            
            # Calcular SL y TP (dinámicos si está configurado)
            if Config.SL_TP_MODE == 'DYNAMIC' and atr_pct > 0:
                stop_loss = self.position_manager.calculate_stop_loss(price, direction, atr_pct)
                take_profit = self.position_manager.calculate_take_profit(price, direction, atr_pct)
            else:
                stop_loss = self.position_manager.calculate_stop_loss(price, direction)
                take_profit = self.position_manager.calculate_take_profit(price, direction)
            
            # Calcular ratio R/R
            rr_ratio = self.position_manager.get_risk_reward_ratio(price, stop_loss, take_profit, direction)
            
            logger.info(f"   SL: €{stop_loss:.2f}")
            logger.info(f"   TP: €{take_profit:.2f}")
            logger.info(f"   Ratio R/R: {rr_ratio:.2f}")
            logger.info(f"   ✅ ACEPTADA para ejecución")
            
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
                'atr_percent': atr_pct,
                'rr_ratio': rr_ratio
            })
        
        logger.info(f"\n📊 Resultado: {len(plans)} operación(es) planificada(s) de {len(analyses)} señal(es)")
        
        return plans
    
    def _execute_trades(self, plans: List[Dict], margin_used: float, total_limit: float):
        """Ejecuta las operaciones planificadas"""
        if not plans:
            logger.info("ℹ️  No hay planes de operaciones para ejecutar")
            return
        
        plans.sort(key=lambda x: x['confidence'], reverse=True)
        
        executed = 0
        current_margin = margin_used
        
        logger.info("\n" + "="*60)
        logger.info("💼 EJECUTANDO OPERACIONES")
        logger.info("="*60)
        logger.info(f"Margen actual: €{current_margin:.2f}")
        logger.info(f"Límite total: €{total_limit:.2f}")
        logger.info(f"Margen disponible: €{total_limit - current_margin:.2f}")
        logger.info(f"Operaciones a ejecutar: {len(plans)}")
        
        for i, plan in enumerate(plans, 1):
            logger.info("\n" + "-"*60)
            logger.info(f"📋 ORDEN {i}/{len(plans)}")
            logger.info("-"*60)
            
            new_total = current_margin + plan['margin_est']
            
            if new_total > total_limit:
                logger.warning(
                    f"⛔ SALTADA {plan['epic']}: Límite total excedido\n"
                    f"   Margen actual: €{current_margin:.2f}\n"
                    f"   + Nuevo margen: €{plan['margin_est']:.2f}\n"
                    f"   = Total: €{new_total:.2f} > Límite: €{total_limit:.2f}"
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
            logger.info(f"📤 {plan['direction']} {plan['epic']}")
            logger.info(f"   Precio entrada: €{plan['price']:.2f}")
            logger.info(f"   Tamaño: {plan['size']} unidades")
            logger.info(f"   Stop Loss: €{plan['stop_loss']:.2f}")
            logger.info(f"   Take Profit: €{plan['take_profit']:.2f}")
            logger.info(f"   Margen estimado: €{plan['margin_est']:.2f}")
            logger.info(f"   Confianza: {plan['confidence']:.0%}")
            
            if plan.get('atr_percent'):
                logger.info(f"   ATR: {plan['atr_percent']:.2f}%")
            
            if plan.get('rr_ratio'):
                logger.info(f"   Ratio R/R: {plan['rr_ratio']:.2f}")
            
            logger.info(f"   Razones: {', '.join(plan['reasons'][:3])}")  # Primeras 3 razones
            
            # Ejecutar orden
            logger.info("   ⏳ Enviando orden a la API...")
            result = self.api.place_order(order_data)
            
            if result:
                deal_ref = result.get('dealReference', 'n/a')
                logger.info(f"   ✅ EJECUTADA - Deal ID: {deal_ref}")
                current_margin += plan['margin_est']
                executed += 1
            else:
                logger.error(f"   ❌ ERROR en la ejecución")
            
            time.sleep(1)  # Rate limiting
        
        # Resumen final
        logger.info("\n" + "="*60)
        logger.info("📊 RESUMEN DE EJECUCIÓN")
        logger.info("="*60)
        logger.info(f"✅ Ejecutadas: {executed}/{len(plans)} orden(es)")
        logger.info(f"💰 Margen usado inicialmente: €{margin_used:.2f}")
        logger.info(f"💰 Margen tras ejecuciones: €{current_margin:.2f}")
        logger.info(f"📈 Margen añadido: €{current_margin - margin_used:.2f}")
        logger.info(f"🎯 Margen disponible restante: €{total_limit - current_margin:.2f}")
        logger.info(f"📊 Utilización: {(current_margin/total_limit)*100:.1f}%")
        logger.info("="*60 + "\n")  

    def is_trading_hours(self) -> bool:
        """Verifica si estamos en horario de trading"""
        now = datetime.now()
        
        # No operar fines de semana
        if now.weekday() >= 5:
            return False
        
        # Verificar horario
        return Config.START_HOUR <= now.hour < Config.END_HOUR
    
    def _log_account_status(self):
        """Log del estado de la cuenta"""
        balance, available = self.position_manager.get_account_balance(self.account_info)
        logger.info(f"💼 Balance: €{balance:.2f} | Disponible: €{available:.2f}")
    
    def _log_margin_status(self, used: float, limit: float, available: float, balance: float):
        """Log del estado del margen"""
        logger.info(f"🧮 Margen usado: €{used:.2f} / Límite total: €{limit:.2f} ({Config.MAX_CAPITAL_RISK*100:.0f}%)")
        logger.info(f"💵 Disponible: €{available:.2f} ({available/balance*100:.1f}% del balance)")
    
    def stop(self):
        """Detiene el bot"""
        logger.info("🛑 Deteniendo bot...")
        self.is_running = False
        self.controller.stop_bot()
        self.api.close_session()
        logger.info("✅ Bot detenido correctamente")