# trading/trading_bot.py
"""
Bot de trading principal - ARRANCA EN MODO PAUSADO
"""

import time
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict

from config import Config
from api.capital_client import CapitalClient
from strategies.intraday_strategy import IntradayStrategy
from trading.core.position_manager import PositionManager
from utils.helpers import safe_float
from utils.bot_state import bot_state  # ✅ Usar el estado global
from utils.logger_manager import SessionLogger
from utils.circuit_breaker import CircuitBreaker
from database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class TradingBot:
    """Bot de trading intraday - ARRANCA PAUSADO, se controla desde dashboard"""

    def __init__(self):
        self.api = CapitalClient()
        self.strategy = IntradayStrategy()
        self.position_manager = PositionManager(self.api)

        self.db_manager = DatabaseManager()
        self.circuit_breaker = CircuitBreaker()
        self.session_logger = None
        self.account_info = {}
        self.signal_ids = {}

    def run(self):
        """Inicia el bot de trading EN MODO PAUSADO"""
        logger.info("=" * 60)
        logger.info("BOT INTRADAY TRADING - Modo Modular v6.5")
        logger.info("Con control manual, persistencia en BD, logs y Circuit Breaker")
        logger.info("=" * 60)

        # ✅ INICIAR EN MODO PAUSADO (no llamar a bot_state.start())
        logger.info("⏸️  Bot iniciado en modo PAUSADO")
        logger.info("💡 Usa el dashboard (http://localhost:5000) para iniciar el bot")

        # Autenticar
        if not self.api.authenticate():
            logger.error("❌ Autenticación fallida")
            return

        # Obtener info de cuenta inicial
        self.account_info = self.api.get_account_info()
        balance, available = self.position_manager.get_account_balance(self.account_info)
        self._log_account_status()

        # Inicializar circuit breaker con balance actual
        self.circuit_breaker.initialize(balance)
        logger.info(f"🛡️ Circuit Breaker inicializado con balance: €{balance:.2f}")

        # Iniciar sesión en BD y sistema de logs
        try:
            # config_snapshot eliminado - schema simplificado
            session_id = self.db_manager.start_session(balance)
            logger.info(f"📊 Sesión de BD iniciada - ID: {session_id}")

            # Iniciar logger de sesión
            self.session_logger = SessionLogger(session_id)

        except Exception as e:
            logger.error(f"❌ Error iniciando sesión de BD: {e}")
            logger.warning("⚠️ El bot continuará pero sin guardar datos")
            self.session_logger = SessionLogger()

        # Loop principal
        logger.info("\n" + "=" * 60)
        logger.info("🔄 LOOP PRINCIPAL INICIADO")
        logger.info("=" * 60)
        
        while True:
            try:
                # ✅ Verificar estado desde bot_state (EN MEMORIA)
                if not bot_state.is_running():
                    # Mostrar mensaje solo cada 30 segundos para no saturar logs
                    if not hasattr(self, '_last_pause_message') or \
                       (time.time() - self._last_pause_message) > 30:
                        logger.info("⏸️  Bot pausado. Esperando comando START desde dashboard...")
                        self._last_pause_message = time.time()
                    time.sleep(10)
                    continue

                # ✅ Si llegamos aquí, el bot está en modo RUNNING
                
                # Limpiar flag de mensaje de pausa
                if hasattr(self, '_last_pause_message'):
                    delattr(self, '_last_pause_message')
                
                # ✅ Actualizar heartbeat
                bot_state.update_heartbeat()

                # Verificar circuit breaker ANTES de operar
                if self.circuit_breaker.is_active():
                    st = self.circuit_breaker.get_status()
                    logger.warning(f"🛑 CIRCUIT BREAKER ACTIVO: {st['reason']}")
                    logger.warning(f"   Estado: {st['message']}")
                    logger.warning(f"   El bot NO operará hasta que se desactive")

                    if self.session_logger:
                        self.session_logger.log_error(
                            f"Circuit breaker activo: {st['reason']}",
                            exception=None
                        )

                    time.sleep(300)  # Esperar 5 minutos
                    continue

                if not self.is_trading_hours():
                    logger.info("⏸️ Fuera de horario de trading")
                    time.sleep(300)
                    continue

                # Actualizar info de cuenta
                self.account_info = self.api.get_account_info()
                balance, available = self.position_manager.get_account_balance(self.account_info)

                # Actualizar balance en circuit breaker
                self.circuit_breaker.update_current_balance(balance)

                # Guardar snapshot de cuenta
                self._save_account_snapshot()

                # Escanear y operar
                self.scan_and_trade()

                # Esperar hasta próximo escaneo
                logger.info(f"⏳ Próximo escaneo en {Config.SCAN_INTERVAL}s ({Config.SCAN_INTERVAL // 60} min)...\n")
                time.sleep(Config.SCAN_INTERVAL)

            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                logger.error(f"❌ Error en loop principal: {e}")

                # Log del error
                if self.session_logger:
                    self.session_logger.log_error(
                        f"Error en loop principal: {e}",
                        exception=e
                    )

                time.sleep(300)

    # ... (resto de métodos sin cambios: scan_and_trade, _analyze_markets, etc.)

    def scan_and_trade(self):
        """Escanea mercados y ejecuta operaciones"""
        logger.info("=" * 60)
        logger.info("🔍 ESCANEANDO MERCADOS")
        logger.info("=" * 60)

        if not self.account_info:
            logger.warning("⚠️ No hay información de cuenta disponible")
            return

        balance, available = self.position_manager.get_account_balance(self.account_info)

        if balance <= 0:
            logger.warning("⚠️ Balance insuficiente")
            return

        # PASO 1: Analizar todos los mercados
        logger.info(f"📊 Analizando {len(Config.ASSETS)} activos...")
        all_analyses = self._analyze_markets()

        if not all_analyses:
            logger.info("ℹ️ No hay señales de trading en ningún activo")

            # Log resumen vacío
            if self.session_logger:
                self.session_logger.log_scan_summary({
                    'total_assets': len(Config.ASSETS),
                    'signals_found': 0,
                    'trades_executed': 0
                })

            return

        # Filtrar por confianza mínima
        valid_analyses = [a for a in all_analyses if a['confidence'] >= Config.MIN_CONFIDENCE]

        if not valid_analyses:
            logger.info(f"ℹ️ Ninguna señal supera la confianza mínima ({Config.MIN_CONFIDENCE:.0%})")

            # Log resumen
            if self.session_logger:
                self.session_logger.log_scan_summary({
                    'total_assets': len(Config.ASSETS),
                    'signals_found': len(all_analyses),
                    'trades_executed': 0
                })

            return

        # Limitar al número máximo de posiciones
        valid_analyses.sort(key=lambda x: x['confidence'], reverse=True)
        valid_analyses = valid_analyses[:Config.MAX_POSITIONS]

        num_opportunities = len(valid_analyses)

        logger.info("=" * 60)
        logger.info(f"✅ OPORTUNIDADES DETECTADAS: {num_opportunities}")
        logger.info("=" * 60)
        for i, analysis in enumerate(valid_analyses, 1):
            logger.info(
                f"{i}. {analysis['epic']}: {analysis['signal']} "
                f"(Confianza: {analysis['confidence']:.0%}, "
                f"ATR: {analysis.get('atr_percent', 0):.2f}%)"
            )

        # PASO 2: Calcular capital total disponible
        if Config.CAPITAL_MODE == 'PERCENTAGE':
            total_capital = available * (Config.MAX_CAPITAL_PERCENT / 100)
            logger.info(f"\n💰 Modo: PORCENTAJE")
            logger.info(f"   Capital disponible: €{available:.2f}")
            logger.info(f"   % máximo a usar: {Config.MAX_CAPITAL_PERCENT:.1f}%")
            logger.info(f"   Capital total asignado: €{total_capital:.2f}")
        else:  # FIXED
            total_capital = min(Config.MAX_CAPITAL_FIXED, available)
            logger.info(f"\n💰 Modo: MONTO FIJO")
            logger.info(f"   Monto máximo configurado: €{Config.MAX_CAPITAL_FIXED:.2f}")
            logger.info(f"   Capital disponible: €{available:.2f}")
            logger.info(f"   Capital total asignado: €{total_capital:.2f}")

        # PASO 3: Distribuir capital entre operaciones
        capital_distribution = self._distribute_capital(
            valid_analyses,
            total_capital,
            num_opportunities
        )

        logger.info(f"\n📊 DISTRIBUCIÓN DE CAPITAL:")
        logger.info(f"   Modo: {Config.DISTRIBUTION_MODE}")
        for epic, amount in capital_distribution.items():
            logger.info(f"   {epic}: €{amount:.2f}")

        # PASO 4: Planificar operaciones
        margin_used = self.position_manager.calculate_margin_used(self.account_info)
        total_limit = balance * Config.MAX_CAPITAL_RISK
        remaining_margin = max(total_limit - margin_used, 0.0)

        logger.info(f"\n🧮 ESTADO DE MARGEN:")
        logger.info(f"   Margen usado: €{margin_used:.2f}")
        logger.info(f"   Límite total: €{total_limit:.2f} ({Config.MAX_CAPITAL_RISK * 100:.0f}% del balance)")
        logger.info(f"   Margen disponible: €{remaining_margin:.2f}")

        plans = self._plan_trades_distributed(
            valid_analyses,
            capital_distribution,
            balance,
            remaining_margin
        )

        if not plans:
            logger.info("\nℹ️ No hay operaciones viables tras aplicar límites")

            # Log resumen
            if self.session_logger:
                self.session_logger.log_scan_summary({
                    'total_assets': len(Config.ASSETS),
                    'signals_found': len(valid_analyses),
                    'trades_executed': 0,
                    'margin_used': margin_used
                })

            return

        # PASO 5: Ejecutar operaciones
        executed = self._execute_trades(plans, margin_used, total_limit)

        # Log resumen final
        if self.session_logger:
            self.session_logger.log_scan_summary({
                'total_assets': len(Config.ASSETS),
                'signals_found': len(valid_analyses),
                'trades_executed': executed,
                'margin_used': margin_used + sum(p['margin_est'] for p in plans[:executed])
            })

    def _analyze_markets(self) -> List[Dict]:
        """Analiza TODOS los mercados y guarda señales en BD"""
        analyses = []

        logger.info("\n" + "=" * 80)
        logger.info("📊 ANÁLISIS DE MERCADOS")
        logger.info("=" * 80)
        logger.info(f"Activos a analizar: {', '.join(Config.ASSETS)}")
        logger.info(f"Timeframe: {Config.TIMEFRAME}")
        logger.info(f"Confianza mínima: {Config.MIN_CONFIDENCE:.0%}")
        logger.info("-" * 80)

        logger.info(f"{'#':<3} {'Asset':<10} {'Status':<15} {'Signal':<10} {'Conf':<8} {'ATR':<8} {'Reason'}")
        logger.info("-" * 80)

        for i, epic in enumerate(Config.ASSETS, 1):
            try:
                market_data = self.api.get_market_data(epic, Config.TIMEFRAME)

                if not market_data or 'prices' not in market_data or not market_data['prices']:
                    logger.info(f"{i:<3} {epic:<10} {'❌ Sin datos':<15}")
                    continue

                df = pd.DataFrame(market_data['prices'])

                for col in ['closePrice', 'openPrice', 'highPrice', 'lowPrice']:
                    if col in df.columns:
                        df[col] = df[col].apply(lambda x: safe_float(x))

                df['closePrice'] = pd.to_numeric(df['closePrice'], errors='coerce')
                df = df.dropna(subset=['closePrice'])

                if df.empty:
                    logger.info(f"{i:<3} {epic:<10} {'❌ Datos vacíos':<15}")
                    continue

                analysis = self.strategy.analyze(df, epic)

                # Log en archivo de señales
                if self.session_logger and analysis['signal'] in ['BUY', 'SELL']:
                    self.session_logger.log_signal(analysis)

                # Formatear output
                signal_text = analysis['signal']
                conf_text = f"{analysis['confidence']:.0%}"
                atr_text = f"{analysis.get('atr_percent', 0):.2f}%"
                reason_text = analysis['reasons'][0] if analysis['reasons'] else ""

                status = "✅ Válida" if analysis['signal'] in ['BUY', 'SELL'] else "⚪ Neutral"

                logger.info(
                    f"{i:<3} {epic:<10} {status:<15} {signal_text:<10} "
                    f"{conf_text:<8} {atr_text:<8} {reason_text}"
                )

                analyses.append(analysis)

            except Exception as e:
                logger.error(f"{i:<3} {epic:<10} {'❌ Error':<15} | {str(e)}")

        logger.info("-" * 80)
        logger.info(f"Total señales encontradas: {len(analyses)}")
        logger.info("=" * 80 + "\n")

        return analyses

    def _distribute_capital(self, analyses: List[Dict], total_capital: float, num_ops: int) -> Dict[str, float]:
        """Distribuye el capital total entre las operaciones"""
        distribution = {}

        if Config.DISTRIBUTION_MODE == 'EQUAL':
            per_operation = total_capital / num_ops
            for analysis in analyses:
                distribution[analysis['epic']] = per_operation
        else:  # WEIGHTED
            total_confidence = sum(a['confidence'] for a in analyses)
            for analysis in analyses:
                weight = analysis['confidence'] / total_confidence
                distribution[analysis['epic']] = total_capital * weight

        return distribution

    def _plan_trades_distributed(
        self,
        analyses: List[Dict],
        capital_distribution: Dict[str, float],
        balance: float,
        remaining_margin: float
    ) -> List[Dict]:
        """Planifica operaciones con capital distribuido"""
        plans = []
        margin_by_asset = self.position_manager.get_margin_by_asset()
        asset_limit = balance * Config.MAX_MARGIN_PER_ASSET

        logger.info("\n" + "=" * 60)
        logger.info("📋 PLANIFICANDO OPERACIONES")
        logger.info("=" * 60)

        for analysis in analyses:
            epic = analysis['epic']
            price = safe_float(analysis['current_price'])
            direction = analysis['signal']
            atr_pct = analysis.get('atr_percent', 0)
            assigned_capital = capital_distribution.get(epic, 0)

            logger.info(f"\n🔍 {epic}:")
            logger.info(f"   Precio: €{price:.2f}")
            logger.info(f"   Dirección: {direction}")
            logger.info(f"   Capital asignado: €{assigned_capital:.2f}")

            target_margin = assigned_capital * Config.SIZE_SAFETY_MARGIN

            size, details, margin_est = self.position_manager.calculate_position_size(
                epic, price, target_margin
            )

            logger.info(f"   Size calculado: {size}")
            logger.info(f"   Margen estimado: €{margin_est:.2f}")

            asset_used = margin_by_asset.get(epic, 0.0)
            total_for_asset = asset_used + margin_est

            logger.info(f"   Margen ya usado: €{asset_used:.2f}")
            logger.info(f"   Total si ejecuta: €{total_for_asset:.2f}")
            logger.info(f"   Límite por activo: €{asset_limit:.2f}")

            if total_for_asset > asset_limit:
                logger.warning(f"   ⛔ RECHAZADA: Excede límite por activo")
                continue

            if margin_est > assigned_capital * 1.2:
                logger.warning(
                    f"   ⛔ RECHAZADA: Margen estimado (€{margin_est:.2f}) "
                    f"excede capital asignado (€{assigned_capital:.2f}) en más del 20%"
                )
                continue

            # Calcular SL y TP
            if Config.SL_TP_MODE == 'DYNAMIC' and atr_pct > 0:
                stop_loss = self.position_manager.calculate_stop_loss(price, direction, atr_pct)
                take_profit = self.position_manager.calculate_take_profit(price, direction, atr_pct)
            else:
                stop_loss = self.position_manager.calculate_stop_loss(price, direction)
                take_profit = self.position_manager.calculate_take_profit(price, direction)

            rr_ratio = self.position_manager.get_risk_reward_ratio(price, stop_loss, take_profit, direction)

            logger.info(f"   SL: €{stop_loss:.2f}")
            logger.info(f"   TP: €{take_profit:.2f}")
            logger.info(f"   R/R: {rr_ratio:.2f}")
            logger.info(f"   ✅ ACEPTADA")

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
                'rr_ratio': rr_ratio,
                'assigned_capital': assigned_capital
            })

        logger.info("\n" + "=" * 60)
        logger.info(f"📊 RESULTADO: {len(plans)} operación(es) planificada(s)")
        logger.info("=" * 60)

        return plans

    def _execute_trades(self, plans: List[Dict], margin_used: float, total_limit: float) -> int:
        """Ejecuta las operaciones planificadas y las guarda en BD"""
        if not plans:
            logger.info("ℹ️ No hay planes de operaciones para ejecutar")
            return 0

        plans.sort(key=lambda x: x['confidence'], reverse=True)

        executed = 0
        current_margin = margin_used

        logger.info("\n" + "=" * 60)
        logger.info("💼 EJECUTANDO OPERACIONES")
        logger.info("=" * 60)
        logger.info(f"Margen actual: €{current_margin:.2f}")
        logger.info(f"Límite total: €{total_limit:.2f}")
        logger.info(f"Margen disponible: €{total_limit - current_margin:.2f}")
        logger.info(f"Operaciones a ejecutar: {len(plans)}")

        for i, plan in enumerate(plans, 1):
            logger.info("\n" + "-" * 60)
            logger.info(f"📋 ORDEN {i}/{len(plans)}")
            logger.info("-" * 60)

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

            # Log detallado
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

            logger.info(f"   Razones: {', '.join(plan['reasons'][:3])}")

            # Ejecutar orden
            logger.info("   ⏳ Enviando orden a la API...")
            result = self.api.place_order(order_data)

            if result:
                deal_ref = result.get('dealReference', 'n/a')
                logger.info(f"   ✅ EJECUTADA - Deal ID: {deal_ref}")

                # Guardar trade en BD
                try:
                    trade_data = {
                        'signal_id': self.signal_ids.get(plan['epic']),
                        'deal_reference': deal_ref,
                        'epic': plan['epic'],
                        'direction': plan['direction'],
                        'entry_price': plan['price'],
                        'size': plan['size'],
                        'stop_loss': plan['stop_loss'],
                        'take_profit': plan['take_profit'],
                        'margin_est': plan['margin_est'],
                        'confidence': plan['confidence'],
                        'sl_tp_mode': Config.SL_TP_MODE,
                        'atr_percent': plan.get('atr_percent'),
                        'reasons': plan['reasons']
                    }

                    trade_id = self.db_manager.save_trade_open(trade_data)

                    if trade_id and self.signal_ids.get(plan['epic']):
                        # self.db_manager.mark_signal_executed(  # Tabla signals eliminada
                        #     self.signal_ids[plan['epic']],
                        #     trade_id
                        # )
                        logger.info(f"   💾 Trade guardado en BD - ID: {trade_id}")

                    # Log en archivo de trades
                    if self.session_logger:
                        self.session_logger.log_trade_open(trade_data)

                except Exception as e:
                    logger.error(f"   ⚠️ Error guardando trade en BD: {e}")

                current_margin += plan['margin_est']
                executed += 1
            else:
                logger.error(f"   ❌ ERROR en la ejecución")

            time.sleep(1)

        # Resumen final
        logger.info("\n" + "=" * 60)
        logger.info("📊 RESUMEN DE EJECUCIÓN")
        logger.info("=" * 60)
        logger.info(f"✅ Ejecutadas: {executed}/{len(plans)} orden(es)")
        logger.info(f"💰 Margen usado inicialmente: €{margin_used:.2f}")
        logger.info(f"💰 Margen tras ejecuciones: €{current_margin:.2f}")
        logger.info(f"📈 Margen añadido: €{current_margin - margin_used:.2f}")
        logger.info(f"🎯 Margen disponible restante: €{total_limit - current_margin:.2f}")
        logger.info(f"📊 Utilización: {(current_margin / total_limit) * 100:.1f}%")
        logger.info("=" * 60 + "\n")

        return executed

    def is_trading_hours(self) -> bool:
        """Verifica si estamos en horario de trading"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        return Config.START_HOUR <= now.hour < Config.END_HOUR

    def _log_account_status(self):
        """Log del estado de la cuenta"""
        balance, available = self.position_manager.get_account_balance(self.account_info)
        logger.info(f"💼 Balance: €{balance:.2f} | Disponible: €{available:.2f}")

    # def _get_config_snapshot eliminado - config_snapshot no se usa

    def _save_account_snapshot(self):
        """Guarda snapshot del estado de la cuenta"""
        try:
            if not self.db_manager.session_id is not None:
                return

            balance, available = self.position_manager.get_account_balance(self.account_info)
            open_positions = len(self.position_manager.get_positions())

            self.db_manager.save_account_snapshot({
                'balance': balance,
                'available': available,
                'open_positions': open_positions
            })

            # Log en archivo también
            if self.session_logger:
                self.session_logger.log_account_snapshot({
                    'balance': balance,
                    'available': available,
                    'open_positions': open_positions
                })
        except Exception as e:
            logger.debug(f"Error guardando snapshot: {e}")

    def stop(self):
        """Detiene el bot"""
        logger.info("🛑 Deteniendo bot...")
        
        # ✅ Actualizar estado EN MEMORIA
        bot_state.stop()

        # Finalizar sesión en BD
        try:
            if self.db_manager.session_id is not None:
                balance, _ = self.position_manager.get_account_balance(self.account_info)
                self.db_manager.end_session(balance)
                logger.info("📊 Sesión de BD finalizada")
        except Exception as e:
            logger.error(f"Error finalizando sesión BD: {e}")

        # Cerrar logger de sesión
        if self.session_logger:
            self.session_logger.close()

        self.api.close_session()
        logger.info("✅ Bot detenido correctamente")