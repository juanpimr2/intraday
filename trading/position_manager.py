# trading/position_manager.py
"""
Gestor de posiciones y margen con SL/TP dinámicos
+ Sizing listo para DEMO 1 semana (límite diario + 2–5% por trade ponderado por confianza)
+ Helpers de persistencia (DB) para registrar trades y equity en vivo
"""

import math
import logging
from datetime import datetime, timezone
from typing import Dict, Tuple, List, Optional

from config import Config
from utils.helpers import safe_float, looks_like_equity

# Persistencia simple (SQLite) — opcional, úsalo desde tu loop en vivo
try:
    from trading.db import DB  # nuevo módulo que te pasé
except Exception:  # pragma: no cover
    DB = None  # si no existe, las funciones de DB quedan no-op

logger = logging.getLogger(__name__)


class PositionManager:
    """Gestiona posiciones, margen y sizing con SL/TP adaptativos"""

    # -------------------------
    # CONSTRUCCIÓN
    # -------------------------
    def __init__(self, api_client, *, enable_db: bool = True):
        self.api = api_client
        self.market_details_cache: Dict[str, Dict] = {}
        # DB opcional (no rompe nada si no está disponible)
        self.db = DB() if (enable_db and DB is not None) else None

        # Parámetros de sizing (LIVE) — coherentes con tu objetivo DEMO
        # Si en el futuro añades Config.PER_TRADE_CAP_PCT para live, se respetará
        self._per_trade_cap_pct_default = float(getattr(Config, "PER_TRADE_CAP_PCT", 0.03))  # fallback 3%

        # Rango recomendado por trade (2–5%) ponderado por confianza (0..1)
        self._per_trade_min = 0.02
        self._per_trade_max = 0.05

    # -------------------------
    # INFO CUENTA / MERCADOS
    # -------------------------
    def get_account_balance(self, account_info: Dict) -> Tuple[float, float]:
        """
        Obtiene balance y disponible de la cuenta

        Returns:
            tuple: (balance, disponible)
        """
        balance = safe_float(account_info.get('balance', {}).get('balance', 0))
        available = safe_float(account_info.get('balance', {}).get('available', 0))
        return balance, available

    def calculate_margin_used(self, account_info: Dict) -> float:
        """
        Calcula el margen usado (balance - disponible)

        Returns:
            float: Margen usado en EUR
        """
        balance, available = self.get_account_balance(account_info)
        return max(balance - available, 0.0)

    def get_market_details(self, epic: str) -> Dict:
        """
        Obtiene detalles del mercado (con caché)

        Returns:
            Dict con: leverage, marginRate, minSize, stepSize, precision
        """
        if epic in self.market_details_cache:
            return self.market_details_cache[epic]

        try:
            data = self.api.get_market_details(epic)
            details = self._parse_market_details(data, epic)
            self.market_details_cache[epic] = details
            return details
        except Exception as e:
            logger.warning(f"Error obteniendo detalles de {epic}: {e}. Usando fallback.")
            details = self._fallback_market_details(epic)
            self.market_details_cache[epic] = details
            return details

    def _parse_market_details(self, data: Dict, epic: str) -> Dict:
        """Parsea los detalles del mercado desde la respuesta de la API"""

        def deep_search(d, keys):
            """Búsqueda recursiva de keys en dict anidado"""
            if not isinstance(d, dict):
                return None
            for k in keys:
                if k in d and d[k]:
                    return d[k]
            for v in d.values():
                if isinstance(v, dict):
                    result = deep_search(v, keys)
                    if result is not None:
                        return result
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            result = deep_search(item, keys)
                            if result is not None:
                                return result
            return None

        details = {}
        details['leverage'] = deep_search(data, ['leverage', 'leverageFactor'])
        margin_rate = deep_search(data, ['marginRate', 'marginFactor'])

        try:
            if margin_rate is not None:
                margin_rate_float = float(margin_rate)
                # 🔧 FIX: Si marginRate viene como porcentaje (>1), convertir a decimal
                if margin_rate_float > 1:
                    details['marginRate'] = margin_rate_float / 100
                    logger.info(f"{epic}: marginRate {margin_rate_float}% → {details['marginRate']}")
                else:
                    details['marginRate'] = margin_rate_float
            else:
                details['marginRate'] = None
        except Exception:
            details['marginRate'] = None

        details['minSize'] = safe_float(
            deep_search(data, ['minDealSize', 'minSize']),
            Config.MIN_POSITION_SIZE
        )
        details['stepSize'] = safe_float(
            deep_search(data, ['dealSizeStep', 'stepSize']),
            0.01
        )
        details['precision'] = int(safe_float(
            deep_search(data, ['lotSizePrecision']),
            2
        ))

        # Fallback conservador si no hay leverage ni marginRate
        if not details['marginRate'] and not details['leverage']:
            details['marginRate'] = 0.20 if looks_like_equity(epic) else 0.05
            logger.info(f"{epic}: Usando marginRate fallback {details['marginRate']*100}%")

        return details

    def _fallback_market_details(self, epic: str) -> Dict:
        """Detalles de mercado con fallback conservador"""
        return {
            'leverage': None,
            'marginRate': 0.20 if looks_like_equity(epic) else 0.05,
            'minSize': Config.MIN_POSITION_SIZE,
            'stepSize': 0.01,
            'precision': 2
        }

    # -------------------------
    # MÁRGENES / SIZING
    # -------------------------
    def calculate_margin(self, price: float, size: float, market_details: Dict, epic: str = None) -> float:
        """
        Calcula el margen requerido para una posición
        """
        price = safe_float(price)
        size = safe_float(size)

        leverage = market_details.get('leverage')
        margin_rate = market_details.get('marginRate')

        if leverage and leverage > 0:
            return (price * size) / leverage
        if margin_rate and margin_rate > 0:
            return price * size * margin_rate

        # Fallback conservador
        fallback_rate = 0.20 if (epic and looks_like_equity(epic)) else 0.05
        return price * size * fallback_rate

    def calculate_position_size(self, epic: str, price: float, target_margin: float) -> Tuple[float, Dict, float]:
        """
        Calcula el tamaño de posición para un margen objetivo (respeta step/minSize/precision)
        Returns: (size, market_details, estimated_margin)
        """
        price = safe_float(price)
        target_margin = safe_float(target_margin)

        details = self.get_market_details(epic)

        # Obtener parámetros
        margin_rate = details.get('marginRate')
        leverage = details.get('leverage')
        step = safe_float(details.get('stepSize', 0.01), 0.01)
        min_size = safe_float(details.get('minSize', Config.MIN_POSITION_SIZE))
        precision = int(safe_float(details.get('precision', 2)))

        logger.debug(f"Calculando size para {epic}:")
        logger.debug(f"  Price: €{price:.2f}")
        logger.debug(f"  Target margin: €{target_margin:.2f}")
        logger.debug(f"  Margin rate: {margin_rate}")
        logger.debug(f"  Leverage: {leverage}")
        logger.debug(f"  Min size: {min_size}")
        logger.debug(f"  Step: {step}")

        # ===== calcular tamaño base por target de margen
        if margin_rate and margin_rate > 0:
            size_raw = target_margin / max(price * margin_rate, 1e-9)
            logger.debug(f"  Usando margin rate: size_raw = {size_raw:.6f}")
        elif leverage and leverage > 0:
            size_raw = (target_margin * leverage) / max(price, 1e-9)
            logger.debug(f"  Usando leverage: size_raw = {size_raw:.6f}")
        else:
            fallback_rate = 0.20 if looks_like_equity(epic) else 0.05
            size_raw = target_margin / max(price * fallback_rate, 1e-9)
            logger.debug(f"  Usando fallback rate {fallback_rate}: size_raw = {size_raw:.6f}")

        # Ajuste a step, mínimo y precisión
        size_adjusted = math.floor(size_raw / step) * step
        if size_adjusted < min_size:
            size_adjusted = min_size
        size = round(size_adjusted, precision)

        margin_est = self.calculate_margin(price, size, details, epic)
        logger.debug(f"  Size final: {size}  |  Margen estimado: €{margin_est:.2f}")

        # Warning si se excede mucho
        if margin_est > target_margin * 1.3:
            logger.warning(
                f"⚠️  {epic}: margen estimado (€{margin_est:.2f}) > target (€{target_margin:.2f}) +30%. "
                f"minSize/step podrían ser altos para tu capital."
            )

        return size, details, margin_est

    # -------------------------
    # SIZING: DEMO 1 SEMANA
    # -------------------------
    def _daily_budget(self, balance: float) -> float:
        """
        Límite de capital/día:
        - Si ENABLE_DAILY_CAPITAL_LIMIT=True → (MAX_CAPITAL_PERCENT/100)*balance / TRADING_DAYS_PER_WEEK
        - Si False → (MAX_CAPITAL_PERCENT/100)*balance  (sin fraccionar por día)
        - Si CAPITAL_MODE='FIXED' → MAX_CAPITAL_FIXED (y se fracciona según flag)
        """
        mode = str(getattr(Config, "CAPITAL_MODE", "PERCENTAGE")).upper()
        if mode == "PERCENTAGE":
            weekly_cap = balance * (float(getattr(Config, "MAX_CAPITAL_PERCENT", 40.0)) / 100.0)
        else:
            weekly_cap = float(getattr(Config, "MAX_CAPITAL_FIXED", 400.0))

        if bool(getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", True)):
            days = max(int(getattr(Config, "TRADING_DAYS_PER_WEEK", 5)), 1)
            return weekly_cap / days
        return weekly_cap

    def _per_trade_budget(self, balance: float, confidence: float) -> float:
        """
        2–5% por trade (lineal por confianza). Si existe Config.PER_TRADE_CAP_PCT, se respeta como techo.
        """
        confidence = float(max(0.0, min(1.0, confidence)))
        # rango 2–5% ponderado por confianza
        pct = self._per_trade_min + (self._per_trade_max - self._per_trade_min) * confidence
        # si hay override global (por ejemplo 3%), usar el mínimo entre ambos techos
        pct = min(pct, self._per_trade_cap_pct_default)
        return balance * pct

    def _remaining_global_risk(self, balance: float, margin_used: float) -> float:
        """
        Límite de margen total permitido (`MAX_CAPITAL_RISK` * balance) menos el ya usado.
        """
        cap = float(getattr(Config, "MAX_CAPITAL_RISK", 0.70))
        ceiling = balance * cap
        return max(ceiling - margin_used, 0.0)

    def _remaining_per_asset(self, epic: str, balance: float, current_asset_margin: float) -> float:
        """
        Límite por instrumento (`MAX_MARGIN_PER_ASSET` * balance) menos el ya usado por ese epic.
        """
        cap = float(getattr(Config, "MAX_MARGIN_PER_ASSET", 0.35))
        ceiling = balance * cap
        return max(ceiling - current_asset_margin, 0.0)

    def _current_asset_margin(self, epic: str) -> float:
        """
        Margen usado actualmente por 'epic' (suma de posiciones abiertas). Recorre API positions.
        """
        try:
            margin_by_asset = self.get_margin_by_asset()
            return safe_float(margin_by_asset.get(epic, 0.0))
        except Exception:
            return 0.0

    def suggest_target_margin(
        self,
        *,
        epic: str,
        price: float,
        confidence: float,
        account_info: Dict,
    ) -> float:
        """
        Calcula un 'target_margin' (EUR) seguro para abrir una NUEVA posición hoy,
        respetando límites: diario, global, por instrumento y size safety.

        Úsalo antes de `calculate_position_size(...)`.
        """
        balance, available = self.get_account_balance(account_info)
        margin_used = self.calculate_margin_used(account_info)

        daily_cap = self._daily_budget(balance)
        per_trade_base = self._per_trade_budget(balance, confidence)
        remaining_global = self._remaining_global_risk(balance, margin_used)
        remaining_asset = self._remaining_per_asset(epic, balance, self._current_asset_margin(epic))

        # Si el margen usado ya supera el cupo diario, no abrir (0)
        if bool(getattr(Config, "ENABLE_DAILY_CAPITAL_LIMIT", True)) and margin_used >= daily_cap:
            logger.info("⛔ Cupo diario agotado: no se sugiere nueva posición.")
            return 0.0

        # target = mínimo de todas las restricciones
        target = min(per_trade_base, daily_cap - margin_used, remaining_global, remaining_asset, available)

        # margen de seguridad
        target *= float(getattr(Config, "SIZE_SAFETY_MARGIN", 0.85))

        # Evitar valores negativos o muy pequeños
        target = max(0.0, target)
        if target < 1.0:  # 1 EUR como umbral práctico
            logger.info("⛔ Target de margen insuficiente (< €1).")
            return 0.0

        logger.info(
            f"🎯 Target margen {epic}: "
            f"per_trade={per_trade_base:.2f}, daily_left={max(daily_cap - margin_used,0):.2f}, "
            f"global_left={remaining_global:.2f}, asset_left={remaining_asset:.2f} → target={target:.2f}"
        )
        return target

    def suggest_size_for_signal(
        self,
        *,
        epic: str,
        direction: str,
        price: float,
        confidence: float,
        account_info: Dict,
        atr_percent: Optional[float] = None,
    ) -> Dict:
        """
        Retorna una propuesta completa de operación:
        {
            "size": float,
            "stop_loss": float,
            "take_profit": float,
            "target_margin": float,
            "estimated_margin": float,
            "precision": int
        }
        Si target_margin = 0 → no abrir.
        """
        target_margin = self.suggest_target_margin(
            epic=epic, price=price, confidence=confidence, account_info=account_info
        )
        if target_margin <= 0:
            return {"size": 0.0, "target_margin": 0.0, "estimated_margin": 0.0, "stop_loss": 0.0, "take_profit": 0.0, "precision": 2}

        size, details, est_margin = self.calculate_position_size(epic, price, target_margin)

        # SL/TP
        if str(getattr(Config, "SL_TP_MODE", "STATIC")).upper() == "DYNAMIC" and atr_percent is not None:
            stop = self.calculate_stop_loss_dynamic(price, direction, atr_percent)
            take = self.calculate_take_profit_dynamic(price, direction, atr_percent)
        else:
            stop = self.calculate_stop_loss_static(price, direction)
            take = self.calculate_take_profit_static(price, direction)

        return {
            "size": size,
            "stop_loss": stop,
            "take_profit": take,
            "target_margin": target_margin,
            "estimated_margin": est_margin,
            "precision": int(details.get("precision", 2)),
        }

    # -------------------------
    # POSICIONES ABIERTAS / MARGEN ACTUAL
    # -------------------------
    def get_positions(self) -> List[Dict]:
        """Obtiene posiciones actuales"""
        return self.api.get_positions()

    def get_margin_by_asset(self) -> Dict[str, float]:
        """
        Calcula el margen usado por cada activo

        Returns:
            Dict: {epic: margen_usado}
        """
        margin_by_asset = {}

        for position in self.get_positions():
            pos_data = position.get('position') or {}
            epic = pos_data.get('epic') or 'Unknown'
            level = safe_float(pos_data.get('level', 0))
            size = safe_float(pos_data.get('size', 0))

            if level <= 0 or size <= 0 or epic == 'Unknown':
                continue

            details = self.get_market_details(epic)
            margin = self.calculate_margin(level, size, details, epic)
            margin_by_asset[epic] = margin_by_asset.get(epic, 0.0) + margin

        return margin_by_asset

    # -------------------------
    # STOP LOSS / TAKE PROFIT
    # -------------------------
    def calculate_stop_loss(self, price: float, direction: str, atr_percent: float = None) -> float:
        """
        Calcula el nivel de stop loss (estático o dinámico según Config)
        """
        if Config.SL_TP_MODE == 'DYNAMIC' and atr_percent is not None:
            return self.calculate_stop_loss_dynamic(price, direction, atr_percent)
        else:
            return self.calculate_stop_loss_static(price, direction)

    def calculate_take_profit(self, price: float, direction: str, atr_percent: float = None) -> float:
        """
        Calcula el nivel de take profit (estático o dinámico según Config)
        """
        if Config.SL_TP_MODE == 'DYNAMIC' and atr_percent is not None:
            return self.calculate_take_profit_dynamic(price, direction, atr_percent)
        else:
            return self.calculate_take_profit_static(price, direction)

    # ---- SL/TP ESTÁTICOS
    def calculate_stop_loss_static(self, price: float, direction: str) -> float:
        if direction == 'BUY':
            return round(price * (1 - Config.STOP_LOSS_PERCENT_BUY), 2)
        else:  # SELL
            return round(price * (1 + Config.STOP_LOSS_PERCENT_SELL), 2)

    def calculate_take_profit_static(self, price: float, direction: str) -> float:
        if direction == 'BUY':
            return round(price * (1 + Config.TAKE_PROFIT_PERCENT_BUY), 2)
        else:  # SELL
            return round(price * (1 - Config.TAKE_PROFIT_PERCENT_SELL), 2)

    # ---- SL/TP DINÁMICOS
    def calculate_stop_loss_dynamic(self, price: float, direction: str, atr_percent: float) -> float:
        sl_distance_percent = atr_percent * Config.ATR_MULTIPLIER_SL
        sl_distance_percent = max(sl_distance_percent, 1.0)   # Mínimo 1%
        sl_distance_percent = min(sl_distance_percent, 10.0)  # Máximo 10%

        if direction == 'BUY':
            sl_level = price * (1 - sl_distance_percent / 100)
        else:  # SELL
            sl_level = price * (1 + sl_distance_percent / 100)

        logger.debug(
            f"SL dinámico: Precio={price:.2f}, ATR={atr_percent:.2f}%, "
            f"Distancia={sl_distance_percent:.2f}%, SL={sl_level:.2f}"
        )
        return round(sl_level, 2)

    def calculate_take_profit_dynamic(self, price: float, direction: str, atr_percent: float) -> float:
        tp_distance_percent = atr_percent * Config.ATR_MULTIPLIER_TP
        tp_distance_percent = max(tp_distance_percent, 2.0)   # Mínimo 2%
        tp_distance_percent = min(tp_distance_percent, 15.0)  # Máximo 15%

        if direction == 'BUY':
            tp_level = price * (1 + tp_distance_percent / 100)
        else:  # SELL
            tp_level = price * (1 - tp_distance_percent / 100)

        logger.debug(
            f"TP dinámico: Precio={price:.2f}, ATR={atr_percent:.2f}%, "
            f"Distancia={tp_distance_percent:.2f}%, TP={tp_level:.2f}"
        )
        return round(tp_level, 2)

    def get_risk_reward_ratio(self, price: float, stop_loss: float, take_profit: float, direction: str) -> float:
        """
        Calcula el ratio riesgo/beneficio de una operación
        """
        if direction == 'BUY':
            risk = abs(price - stop_loss)
            reward = abs(take_profit - price)
        else:  # SELL
            risk = abs(stop_loss - price)
            reward = abs(price - take_profit)

        if risk > 0:
            return reward / risk
        return 0.0

    # -------------------------
    # PERSISTENCIA (helpers)
    # -------------------------
    def save_equity_point(self, equity: float, cash: float, open_positions: int, ts_utc: Optional[datetime] = None) -> None:
        """
        Guarda un punto de equity en SQLite (si DB está disponible).
        Llama esto en tu loop (cada X minutos o on_bar).
        """
        if self.db is None:
            return
        ts_utc = ts_utc or datetime.now(timezone.utc)
        try:
            self.db.save_equity_point(ts_utc=ts_utc, equity=equity, cash=cash, open_positions=open_positions)
        except Exception as e:  # pragma: no cover
            logger.warning(f"No se pudo guardar equity_point: {e}")

    def record_filled_trade(
        self,
        *,
        epic: str,
        side: str,
        entry_ts: datetime,
        exit_ts: datetime,
        entry_price: float,
        exit_price: float,
        size_eur: float,
        units: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
        confidence: float,
        regime: str = "lateral",
        duration_hours: float = 0.0,
    ) -> None:
        """
        Guarda un trade CERRADO en SQLite (si DB está disponible).
        Llama esto justo al cerrar la operación en vivo.
        """
        if self.db is None:
            return
        try:
            self.db.save_trade(
                epic=epic, side=side,
                entry_ts=entry_ts, exit_ts=exit_ts,
                entry_price=entry_price, exit_price=exit_price,
                size_eur=size_eur, units=units,
                pnl=pnl, pnl_pct=pnl_pct,
                reason=reason, confidence=confidence,
                regime=regime, duration_hours=duration_hours
            )
        except Exception as e:  # pragma: no cover
            logger.warning(f"No se pudo guardar trade en DB: {e}")
