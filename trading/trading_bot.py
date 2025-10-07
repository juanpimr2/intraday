"""
Bot de trading principal - Orquestador (Con persistencia en BD, logs, Circuit Breaker y Capital Tracker)

Este módulo implementa la clase `TradingBot` y orquesta el flujo completo:
- Autenticación con el broker (CapitalClient)
- Loop principal (controlado por BotController)
- Escaneo de mercados (IntradayStrategy)
- Gestión de posiciones (PositionManager)
- Límites de riesgo (CircuitBreaker)
- Límite de capital diario (CapitalTracker)
- Persistencia de señales y trades (DatabaseManager)
- Sistema de logs por sesión (SessionLogger)

⚠️ Importante:
- Este archivo fue generado para el repo `intraday` y utiliza las firmas de métodos
  que ya están presentes en el proyecto (según estructura pública).
- Si alguna firma difiere en tu local, ajusta los nombres del método puntualmente.
"""

from __future__ import annotations

import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config import Config
from api.capital_client import CapitalClient
from strategies.intraday_strategy import IntradayStrategy
from trading.position_manager import PositionManager
from utils.helpers import safe_float
from utils.bot_controller import BotController
from utils.logger_manager import SessionLogger
from utils.circuit_breaker import CircuitBreaker
from utils.capital_tracker import CapitalTracker
from database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class TradingBot:
    """
    Bot de trading intradía: orquestador principal con persistencia, logs, circuit breaker y capital tracker.
    """

    def __init__(self) -> None:
        # Componentes principales
        self.api = CapitalClient()
        self.strategy = IntradayStrategy()
        self.position_manager = PositionManager(self.api)

        # Infraestructura / utilidades
        self.controller = BotController()
        self.db_manager = DatabaseManager()
        self.session_logger: Optional[SessionLogger] = None

        # Protección y control de riesgo
        self.circuit_breaker = CircuitBreaker()
        self.capital_tracker = CapitalTracker()

        # Estado
        self.account_info: Dict = {}
        self.is_running: bool = False
        self.signal_ids: Dict[str, int] = {}  # epic -> signal_id

    # -------------------------- PÚBLICO --------------------------

    def run(self) -> None:
        """
        Inicia el bot. Maneja autenticación, setup y loop principal.
        """
        logger.info("=" * 70)
        logger.info("BOT INTRADAY TRADING - Modo Modular (con CB + CapitalTracker)")
        logger.info("=" * 70)

        self.is_running = True

        # 1) Autenticación
        if not self.api.authenticate():
            logger.error("❌ Autenticación fallida con el broker")
            return

        # 2) Obtener info de cuenta inicial
        self.account_info = self.api.get_account_info()
        balance, available = self.position_manager.get_account_balance(self.account_info)
        self._log_account_status()

        # 3) Circuit Breaker
        self.circuit_breaker.initialize(balance)
        logger.info("🛡️  Circuit Breaker inicializado con balance: €%.2f", balance)

        # 4) Capital Tracker diario
        if getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", False):
            try:
                self.capital_tracker.initialize(available)
                logger.info("💰 CapitalTracker inicializado con disponible: €%.2f", available)
            except Exception as e:
                logger.warning("No se pudo inicializar CapitalTracker: %s", e)

        # 5) Iniciar sesión BD y logs
        try:
            config_snapshot = self._get_config_snapshot()
            session_id = self.db_manager.start_session(balance, config_snapshot)
            logger.info("📊 Sesión BD iniciada | id=%s", session_id)

            self.session_logger = SessionLogger(session_id)
        except Exception as e:
            logger.error("❌ Error iniciando sesión BD: %s", e)
            logger.warning("Continuará sin guardar en BD, pero con logs locales.")
            self.session_logger = SessionLogger()  # logger sin session_id

        # 6) Loop principal
        while self.is_running:
            try:
                # 6.1) Control manual
                if not self.controller.is_running():
                    logger.info("⏸️  Pausado manualmente. Reintentando en 10s...")
                    time.sleep(10)
                    continue

                # 6.2) Circuit breaker activo -> dormir
                if self.circuit_breaker.is_active():
                    status = self.circuit_breaker.get_status()
                    logger.warning("🛑 CIRCUIT BREAKER ACTIVO: %s", status.get("reason"))
                    logger.warning("   Estado: %s", status.get("message"))
                    if self.session_logger:
                        self.session_logger.log_error("Circuit breaker activo: " + str(status.get("reason")))
                    time.sleep(300)
                    continue

                # 6.3) Horario de trading
                if not self.is_trading_hours():
                    logger.info("⏸️  Fuera de horario de trading. Reintentando en 5m...")
                    time.sleep(300)
                    continue

                # 6.4) Actualizar cuenta
                self.account_info = self.api.get_account_info()
                balance, available = self.position_manager.get_account_balance(self.account_info)

                # Actualizar circuit breaker con balance corriente
                self.circuit_breaker.update_current_balance(balance)

                # Actualizar capital tracker con disponible corriente
                if getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", False):
                    try:
                        self.capital_tracker.update_available_balance(available)
                    except Exception as e:
                        logger.debug("No se pudo actualizar CapitalTracker: %s", e)

                # 6.5) Guardar snapshot de cuenta
                self._save_account_snapshot()

                # 6.6) Escanear y operar
                self.scan_and_trade()

                # 6.7) Espera entre escaneos
                scan_interval = getattr(Config, "SCAN_INTERVAL", 60)
                logger.info("⏳ Próximo escaneo en %ss (~%s min)\n", scan_interval, scan_interval // 60)
                time.sleep(scan_interval)

            except KeyboardInterrupt:
                logger.info("Detenido por el usuario.")
                self.stop()
                break
            except Exception as e:
                logger.exception("❌ Error en loop principal: %s", e)
                if self.session_logger:
                    self.session_logger.log_error(f"Error en loop principal: {e}")
                time.sleep(300)

    def stop(self) -> None:
        """Detiene el bot limpiamente y cierra la sesión en BD."""
        self.is_running = False
        try:
            if self.db_manager and self.db_manager.has_active_session():
                self.db_manager.end_session()
                logger.info("📥 Sesión en BD finalizada correctamente.")
        except Exception as e:
            logger.warning("No se pudo cerrar la sesión BD: %s", e)

    def scan_and_trade(self) -> None:
        """
        Escanea mercados, distribuye capital, planifica y ejecuta operaciones.
        Maneja CB, límites de capital y persistencia.
        """
        logger.info("=" * 70)
        logger.info("🔍 ESCANEANDO MERCADOS")
        logger.info("=" * 70)

        if not self.account_info:
            logger.warning("No hay información de cuenta disponible todavía.")
            return

        balance, available = self.position_manager.get_account_balance(self.account_info)
        if balance <= 0:
            logger.warning("Balance insuficiente para operar.")
            return

        # 1) Analizar mercados
        analyses = self._analyze_markets()
        if not analyses:
            logger.info("No se generaron señales.")
            if self.session_logger:
                self.session_logger.log_scan_summary(
                    {"total_assets": len(getattr(Config, "ASSETS", [])), "signals_found": 0, "trades_executed": 0}
                )
            return

        # 2) Filtrar por confianza
        min_conf = getattr(Config, "MIN_CONFIDENCE", 0.0)
        valid_analyses = [a for a in analyses if a.get("confidence", 0) >= min_conf]
        if not valid_analyses:
            logger.info("Sin señales por debajo del umbral de confianza (%.0f%%).", min_conf * 100)
            if self.session_logger:
                self.session_logger.log_scan_summary(
                    {"total_assets": len(getattr(Config, "ASSETS", [])), "signals_found": len(analyses), "trades_executed": 0}
                )
            return

        # 3) Priorización y límite por cantidad
        max_positions = getattr(Config, "MAX_POSITIONS", 1)
        if getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", False):
            valid_analyses = self.capital_tracker.prioritize_signals(valid_analyses)  # type: ignore[attr-defined]
        else:
            valid_analyses.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        valid_analyses = valid_analyses[:max_positions]

        # 4) Resumen de oportunidades
        logger.info("✅ OPORTUNIDADES DETECTADAS: %s", len(valid_analyses))
        for i, a in enumerate(valid_analyses, 1):
            logger.info(
                "%d) %s: %s (Conf: %.0f%% | ATR: %.2f%%)",
                i,
                a.get("epic"),
                a.get("signal"),
                a.get("confidence", 0) * 100,
                a.get("atr_percent", 0),
            )

        # 5) Capital total asignado (por modo)
        capital_mode = getattr(Config, "CAPITAL_MODE", "PERCENTAGE")
        if capital_mode == "PERCENTAGE":
            total_capital = available * (getattr(Config, "MAX_CAPITAL_PERCENT", 100.0) / 100.0)
            logger.info("💰 Modo: PORCENTAJE | Disponible: €%.2f | %% máx: %.1f%% | Total: €%.2f",
                        available, getattr(Config, "MAX_CAPITAL_PERCENT", 100.0), total_capital)
        else:
            total_capital = min(getattr(Config, "MAX_CAPITAL_FIXED", 0.0), available)
            logger.info("💰 Modo: FIJO | Tope: €%.2f | Disponible: €%.2f | Total: €%.2f",
                        getattr(Config, "MAX_CAPITAL_FIXED", 0.0), available, total_capital)

        # 6) Aplicar límite diario (CapitalTracker)
        if getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", False):
            daily_available = self.capital_tracker.get_available_capital_today()  # type: ignore[attr-defined]
            logger.info("💰 LÍMITE DIARIO | Disponible: €%.2f | Usado: €%.2f",
                        daily_available, getattr(self.capital_tracker, "capital_used_today", 0.0))

            if not self.capital_tracker.can_trade_today():  # type: ignore[attr-defined]
                logger.warning("⛔ Límite diario alcanzado. No se opera hoy.")
                if self.session_logger:
                    self.session_logger.log_scan_summary(
                        {"total_assets": len(getattr(Config, "ASSETS", [])),
                         "signals_found": len(valid_analyses),
                         "trades_executed": 0}
                    )
                return

            total_capital = min(total_capital, daily_available)
            logger.info("Capital total ajustado por límite diario: €%.2f", total_capital)

        # 7) Distribución de capital
        distribution = self._distribute_capital(valid_analyses, total_capital, len(valid_analyses))
        logger.info("📊 DISTRIBUCIÓN: %s", ", ".join(f"{k}: €{v:.2f}" for k, v in distribution.items()))

        # 8) Límites de margen
        margin_used = self.position_manager.calculate_margin_used(self.account_info)
        total_limit = balance * getattr(Config, "MAX_CAPITAL_RISK", 1.0)
        remaining_margin = max(total_limit - margin_used, 0.0)
        logger.info("🧮 MARGEN | usado: €%.2f | límite: €%.2f | disponible: €%.2f",
                    margin_used, total_limit, remaining_margin)

        # 9) Planificación
        plans = self._plan_trades_distributed(valid_analyses, distribution, balance, remaining_margin)
        if not plans:
            logger.info("No hay operaciones viables tras aplicar límites.")
            if self.session_logger:
                self.session_logger.log_scan_summary(
                    {"total_assets": len(getattr(Config, "ASSETS", [])),
                     "signals_found": len(valid_analyses),
                     "trades_executed": 0,
                     "margin_used": margin_used}
                )
            return

        # 10) Ejecución
        executed = self._execute_trades(plans, margin_used, total_limit)

        # 11) Resumen de escaneo
        if self.session_logger:
            self.session_logger.log_scan_summary(
                {
                    "total_assets": len(getattr(Config, "ASSETS", [])),
                    "signals_found": len(valid_analyses),
                    "trades_executed": executed,
                    "margin_used": margin_used + sum(p.get("margin_est", 0.0) for p in plans[:executed]),
                }
            )

    # -------------------------- PRIVADO --------------------------

    def _analyze_markets(self) -> List[Dict]:
        """
        Analiza todos los activos en Config.ASSETS usando IntradayStrategy.
        Devuelve una lista de diccionarios de análisis (cada uno incluye al menos: epic, signal, confidence)
        y registra cada señal en BD.
        """
        assets = list(getattr(Config, "ASSETS", []))
        tf = getattr(Config, "TIMEFRAME", "15min")

        analyses: List[Dict] = []

        logger.info("-" * 80)
        logger.info("📊 ANALIZANDO %d activos | TF=%s | min_conf=%.0f%%",
                    len(assets), tf, getattr(Config, "MIN_CONFIDENCE", 0.0) * 100)
        logger.info("-" * 80)

        for epic in assets:
            try:
                market_data = self.api.get_market_data(epic, tf)
                if not market_data or "prices" not in market_data or not market_data["prices"]:
                    logger.info("%-10s ❌ Sin datos", epic)
                    continue

                df = pd.DataFrame(market_data["prices"])

                # Normalización de campos numéricos comunes
                for col in ("closePrice", "openPrice", "highPrice", "lowPrice"):
                    if col in df.columns:
                        df[col] = df[col].apply(lambda x: safe_float(x))

                df["closePrice"] = pd.to_numeric(df.get("closePrice", pd.Series(dtype=float)), errors="coerce")
                df = df.dropna(subset=["closePrice"])

                if df.empty:
                    logger.info("%-10s ❌ Datos vacíos", epic)
                    continue

                analysis = self.strategy.analyze(df, epic)

                # Persistir señal
                try:
                    signal_id = self.db_manager.save_signal(analysis)
                    if signal_id and analysis.get("signal") in {"BUY", "SELL"}:
                        self.signal_ids[epic] = signal_id
                except Exception as e:
                    logger.debug("No se pudo guardar señal en BD para %s: %s", epic, e)

                # Log de señal
                if self.session_logger and analysis.get("signal") in {"BUY", "SELL"}:
                    try:
                        self.session_logger.log_signal(analysis)
                    except Exception as e:
                        logger.debug("No se pudo loguear señal en archivo para %s: %s", epic, e)

                analyses.append(analysis)

            except Exception as e:
                logger.exception("%-10s ❌ Error analizando: %s", epic, e)

        logger.info("Total señales generadas: %d", len(analyses))
        logger.info("-" * 80)

        return analyses

    def _distribute_capital(self, analyses: List[Dict], total_capital: float, num_ops: int) -> Dict[str, float]:
        """
        Devuelve un mapping epic -> capital asignado, según Config.DISTRIBUTION_MODE
        """
        mode = getattr(Config, "DISTRIBUTION_MODE", "EQUAL")
        distribution: Dict[str, float] = {}

        if num_ops <= 0 or total_capital <= 0:
            return distribution

        if mode == "EQUAL":
            per_op = total_capital / num_ops
            for a in analyses:
                distribution[a.get("epic")] = per_op
        else:  # WEIGHTED
            total_conf = sum(a.get("confidence", 0.0) for a in analyses) or 1.0
            for a in analyses:
                w = a.get("confidence", 0.0) / total_conf
                distribution[a.get("epic")] = total_capital * w

        return distribution

    def _plan_trades_distributed(
        self,
        analyses: List[Dict],
        capital_distribution: Dict[str, float],
        balance: float,
        remaining_margin: float,
    ) -> List[Dict]:
        """
        Genera planes de trade considerando distribución de capital y límites.
        Cada plan incluye: epic, direction, price, size, stop_loss, take_profit, margin_est, confidence, etc.
        """
        plans: List[Dict] = []
        asset_limit = balance * getattr(Config, "MAX_MARGIN_PER_ASSET", 1.0)

        logger.info("=" * 60)
        logger.info("📋 PLANIFICANDO OPERACIONES")
        logger.info("=" * 60)

        try:
            margin_by_asset = self.position_manager.get_margin_by_asset()
        except Exception:
            margin_by_asset = {}

        for a in analyses:
            epic = a.get("epic")
            direction = a.get("signal")
            price = safe_float(a.get("current_price"))
            atr_pct = a.get("atr_percent", 0.0)
            assigned_capital = capital_distribution.get(epic, 0.0)

            logger.info("\n🔍 %s | Precio=€%.2f | Dir=%s | Capital=€%.2f",
                        epic, price, direction, assigned_capital)

            target_margin = assigned_capital * getattr(Config, "SIZE_SAFETY_MARGIN", 1.0)

            size, details, margin_est = self.position_manager.calculate_position_size(epic, price, target_margin)
            logger.info("   Size=%s | Margen estimado=€%.2f", size, margin_est)

            # Límite por activo
            used_for_asset = margin_by_asset.get(epic, 0.0)
            total_for_asset = used_for_asset + margin_est
            logger.info("   Margen usado asset=€%.2f | total si ejecuta=€%.2f | límite por activo=€%.2f",
                        used_for_asset, total_for_asset, asset_limit)

            if total_for_asset > asset_limit:
                logger.warning("   ⛔ RECHAZADA: excede límite por activo")
                continue

            # Coherencia con capital asignado
            if assigned_capital > 0 and margin_est > assigned_capital * 1.2:
                logger.warning("   ⛔ RECHAZADA: margen(€%.2f) > 120%% del capital asignado(€%.2f)",
                               margin_est, assigned_capital)
                continue

            # SL/TP
            if getattr(Config, "SL_TP_MODE", "STATIC") == "DYNAMIC" and atr_pct > 0:
                stop_loss = self.position_manager.calculate_stop_loss(price, direction, atr_pct)
                take_profit = self.position_manager.calculate_take_profit(price, direction, atr_pct)
            else:
                stop_loss = self.position_manager.calculate_stop_loss(price, direction)
                take_profit = self.position_manager.calculate_take_profit(price, direction)

            rr_ratio = self.position_manager.get_risk_reward_ratio(price, stop_loss, take_profit, direction)

            logger.info("   SL=€%.2f | TP=€%.2f | R/R=%.2f | ✅ ACEPTADA", stop_loss, take_profit, rr_ratio)

            plans.append(
                {
                    "epic": epic,
                    "direction": direction,
                    "price": price,
                    "size": size,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "margin_est": margin_est,
                    "confidence": a.get("confidence", 0.0),
                    "reasons": a.get("reasons", []),
                    "indicators": a.get("indicators", {}),
                    "atr_percent": atr_pct,
                    "rr_ratio": rr_ratio,
                    "assigned_capital": assigned_capital,
                }
            )

        logger.info("\n📊 %d operación(es) planificada(s)", len(plans))
        return plans

    def _execute_trades(self, plans: List[Dict], margin_used: float, total_limit: float) -> int:
        """
        Ejecuta planes de trading respetando el límite de margen total.
        Guarda trades en BD, marca señales ejecutadas y anota en logs.
        """
        if not plans:
            return 0

        plans.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)

        executed = 0
        current_margin = margin_used

        logger.info("=" * 60)
        logger.info("💼 EJECUTANDO OPERACIONES")
        logger.info("=" * 60)
        logger.info("Margen inicial=€%.2f | Límite total=€%.2f | Disponible=€%.2f",
                    current_margin, total_limit, max(total_limit - current_margin, 0.0))
        logger.info("Operaciones a intentar: %d", len(plans))

        for i, p in enumerate(plans, 1):
            new_total = current_margin + p.get("margin_est", 0.0)
            logger.info("\n📋 ORDEN %d/%d | %s %s", i, len(plans), p.get("direction"), p.get("epic"))

            if new_total > total_limit:
                logger.warning("⛔ SALTADA: nuevo total(€%.2f) > límite(€%.2f)", new_total, total_limit)
                continue

            # Reserva de capital diario
            if getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", False):
                ok = self.capital_tracker.allocate_capital(  # type: ignore[attr-defined]
                    p.get("margin_est", 0.0),
                    p.get("epic"),
                    p.get("confidence", 0.0),
                )
                if not ok:
                    logger.warning("⛔ Capital diario insuficiente para %s", p.get("epic"))
                    continue

            order_data = {
                "epic": p.get("epic"),
                "direction": p.get("direction"),
                "size": p.get("size"),
                "guaranteedStop": False,
                "stopLevel": p.get("stop_loss"),
                "profitLevel": p.get("take_profit"),
            }

            logger.info(
                "   Entrada: €%.2f | Size: %s | SL: €%.2f | TP: €%.2f | margen: €%.2f | conf: %.0f%%",
                p.get("price"),
                p.get("size"),
                p.get("stop_loss"),
                p.get("take_profit"),
                p.get("margin_est"),
                p.get("confidence", 0.0) * 100,
            )

            logger.info("   ⏳ Enviando orden a la API...")
            result = self.api.place_order(order_data)

            if result:
                deal_ref = result.get("dealReference", "n/a")
                logger.info("   ✅ EJECUTADA | DealRef=%s", deal_ref)

                # Persistencia del trade
                try:
                    trade_data = {
                        "signal_id": self.signal_ids.get(p.get("epic")),
                        "deal_reference": deal_ref,
                        "epic": p.get("epic"),
                        "direction": p.get("direction"),
                        "entry_price": p.get("price"),
                        "size": p.get("size"),
                        "stop_loss": p.get("stop_loss"),
                        "take_profit": p.get("take_profit"),
                        "margin_est": p.get("margin_est"),
                        "confidence": p.get("confidence"),
                        "sl_tp_mode": getattr(Config, "SL_TP_MODE", "STATIC"),
                        "atr_percent": p.get("atr_percent"),
                        "reasons": p.get("reasons"),
                    }

                    trade_id = self.db_manager.save_trade_open(trade_data)

                    if trade_id and self.signal_ids.get(p.get("epic")):
                        try:
                            self.db_manager.mark_signal_executed(self.signal_ids[p.get("epic")], trade_id)
                        except Exception:
                            pass

                    logger.info("   💾 Trade guardado en BD | id=%s", trade_id)

                    if self.session_logger:
                        self.session_logger.log_trade_open(trade_data)

                except Exception as e:
                    logger.error("   ⚠️  Error guardando trade en BD: %s", e)

                # Actualizar márgenes
                current_margin = new_total
                executed += 1

            else:
                logger.error("   ❌ ERROR al ejecutar orden en API.")

            time.sleep(1)

        # Resumen final
        logger.info("=" * 60)
        logger.info("📊 RESUMEN DE EJECUCIÓN")
        logger.info("=" * 60)
        logger.info("✅ Ejecutadas: %d/%d", executed, len(plans))
        logger.info("💰 Margen inicial: €%.2f | final: €%.2f | Δ: €%.2f | restante: €%.2f",
                    margin_used,
                    current_margin,
                    current_margin - margin_used,
                    max(total_limit - current_margin, 0.0),
                    )
        if getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", False):
            try:
                self.capital_tracker.log_daily_usage()  # type: ignore[attr-defined]
            except Exception:
                pass

        return executed

    # ----------------------- UTILIDADES -----------------------

    def is_trading_hours(self) -> bool:
        """
        Devuelve True si estamos dentro del horario de trading configurado.
        (Lunes-Viernes y horas [START_HOUR, END_HOUR))
        """
        now = datetime.now()
        if now.weekday() >= 5:  # sábado (5) o domingo (6)
            return False
        start_h = getattr(Config, "START_HOUR", 8)
        end_h = getattr(Config, "END_HOUR", 22)
        return start_h <= now.hour < end_h

    def _log_account_status(self) -> None:
        """Loguea el estado de la cuenta actual."""
        try:
            balance, available = self.position_manager.get_account_balance(self.account_info)
            logger.info("💼 Balance: €%.2f | Disponible: €%.2f", balance, available)
        except Exception as e:
            logger.debug("No se pudo loguear estado de cuenta: %s", e)

    def _get_config_snapshot(self) -> Dict:
        """Snapshot serializable de la configuración actual."""
        return {
            "assets": getattr(Config, "ASSETS", []),
            "max_positions": getattr(Config, "MAX_POSITIONS", 1),
            "capital_mode": getattr(Config, "CAPITAL_MODE", "PERCENTAGE"),
            "max_capital_percent": getattr(Config, "MAX_CAPITAL_PERCENT", 100.0),
            "max_capital_fixed": getattr(Config, "MAX_CAPITAL_FIXED", 0.0),
            "sl_tp_mode": getattr(Config, "SL_TP_MODE", "STATIC"),
            "timeframe": getattr(Config, "TIMEFRAME", "15min"),
            "enable_mtf": getattr(Config, "ENABLE_MTF", False),
            "enable_adx_filter": getattr(Config, "ENABLE_ADX_FILTER", False),
            "min_confidence": getattr(Config, "MIN_CONFIDENCE", 0.0),
            "scan_interval": getattr(Config, "SCAN_INTERVAL", 60),
            "circuit_breaker": {
                "enabled": getattr(Config, "ENABLE_CIRCUIT_BREAKER", True),
                "max_daily_loss": getattr(Config, "MAX_DAILY_LOSS_PERCENT", 0.0),
                "max_weekly_loss": getattr(Config, "MAX_WEEKLY_LOSS_PERCENT", 0.0),
                "max_consecutive_losses": getattr(Config, "MAX_CONSECUTIVE_LOSSES", 0),
                "max_drawdown": getattr(Config, "MAX_TOTAL_DRAWDOWN_PERCENT", 0.0),
            },
            "capital_tracker": {
                "enabled": getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", False),
                "trading_days_per_week": getattr(Config, "TRADING_DAYS_PER_WEEK", 5),
            },
        }

    def _save_account_snapshot(self) -> None:
        """
        Guarda snapshot de la cuenta en BD si hay sesión activa.
        Se tolera fallo silencioso para no interrumpir el loop.
        """
        try:
            if not self.db_manager.has_active_session():
                return

            balance, available = self.position_manager.get_account_balance(self.account_info)
            open_positions = 0
            try:
                pos = self.api.get_positions()
                open_positions = len(pos) if pos else 0
            except Exception:
                pass

            snap = {
                "timestamp": datetime.utcnow().isoformat(),
                "balance": balance,
                "available": available,
                "open_positions": open_positions,
            }
            self.db_manager.save_account_snapshot(snap)

            if self.session_logger:
                self.session_logger.log_account_snapshot(snap)

        except Exception as e:
            logger.debug("No se pudo guardar snapshot de cuenta: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    bot = TradingBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()
        logger.info("Bot detenido por teclado.")
