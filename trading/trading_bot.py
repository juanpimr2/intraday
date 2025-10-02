"""
Bot de trading principal - Orquestador
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

logger = logging.getLogger(__name__)


class TradingBot:
    """Bot de trading intraday - Orquestador principal"""
    
    def __init__(self):
        self.api = CapitalClient()
        self.strategy = IntradayStrategy()
        self.position_manager = PositionManager(self.api)
        self.account_info = {}
        self.is_running = False
    
    def run(self):
        """Inicia el bot de trading"""
        logger.info("="*60)
        logger.info("BOT INTRADAY TRADING - Modo Modular v6.0")
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
        
        for analysis in analyses:
            epic = analysis['epic']
            price = safe_float(analysis['current_price'])
            direction = analysis['signal']
            
            # Calcular tamaño de posición
            size, details, margin_est = self.position_manager.calculate_position_size(
                epic, price, per_trade_margin
            )
            
            # Verificar límite por activo
            asset_used = margin_by_asset.get(epic, 0.0)
            
            if asset_used + margin_est > asset_limit:
                logger.warning(
                    f"⛔ {epic}: Límite por activo excedido "
                    f"(actual €{asset_used:.2f} + nuevo €{margin_est:.2f} > €{asset_limit:.2f})"
                )
                continue
            
            # Calcular SL y TP
            stop_loss = self.position_manager.calculate_stop_loss(price, direction)
            take_profit = self.position_manager.calculate_take_profit(price, direction)
            
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
                'indicators': analysis['indicators']
            })
        
        return plans
    
    def _execute_trades(self, plans: List[Dict], margin_used: float, total_limit: float):
        """Ejecuta las operaciones planificadas"""
        plans.sort(key=lambda x: x['confidence'], reverse=True)
        
        executed = 0
        current_margin = margin_used
        
        for plan in plans:
            new_total = current_margin + plan['margin_est']
            
            if new_total > total_limit:
                logger.warning(
                    f"⛔ Saltada {plan['epic']}: Límite total excedido "
                    f"(nuevo total €{new_total:.2f} > €{total_limit:.2f})"
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
            
            # Log de la orden
            logger.info("-"*60)
            logger.info(f"📤 ORDEN {plan['direction']}: {plan['epic']} @ €{plan['price']:.2f}")
            logger.info(f"   Size: {plan['size']} | SL: €{plan['stop_loss']} | TP: €{plan['take_profit']}")
            logger.info(f"   Margen estimado: €{plan['margin_est']:.2f} | Confianza: {plan['confidence']:.0%}")
            logger.info(f"   Razones: {', '.join(plan['reasons'])}")
            
            # Ejecutar orden
            result = self.api.place_order(order_data)
            
            if result:
                deal_ref = result.get('dealReference', 'n/a')
                logger.info(f"✅ Orden ejecutada - Deal ID: {deal_ref}")
                current_margin += plan['margin_est']
                executed += 1
            else:
                logger.error(f"❌ Error ejecutando orden")
            
            time.sleep(1)  # Rate limiting
        
        logger.info("="*60)
        logger.info(f"📊 RESUMEN: {executed}/{len(plans)} órdenes ejecutadas")
        logger.info(f"💰 Margen estimado tras ejecuciones: €{current_margin:.2f} (límite €{total_limit:.2f})")
        logger.info("="*60)
    
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
        self.api.close_session()
        logger.info("✅ Bot detenido correctamente")