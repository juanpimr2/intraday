"""
backtesting/backtest_engine.py

Motor de Backtesting UNIFICADO con:
- Asignación de capital diaria priorizada por confianza (utils.CapitalTracker).
- Costes reales (comisiones + spread) vía utils.apply_costs.
- Timestamps de barra reales en UTC para entradas/salidas y equity.
- Detección de régimen de mercado (trending/lateral) por activo (utils.detect_regime).
- Métricas y análisis segmentados por régimen.
- Export por defecto dentro de reports/run_<timestamp>/.

Este archivo incluye un FIX importante:
- Evitar pasar `tz='UTC'` a un Timestamp que ya viene con tzinfo.
  Se usa `_to_utc()` para normalizar: tz_localize('UTC') si naive, o tz_convert('UTC') si tz-aware.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

from strategies.intraday_strategy import IntradayStrategy
from utils import CapitalTracker, apply_costs, detect_regime
from config import Config
from utils.helpers import safe_float

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# Utilidades internas de tiempo
# --------------------------------------------------------------------------------------

def _to_utc(ts: Union[pd.Timestamp, datetime]) -> pd.Timestamp:
    """Devuelve un pd.Timestamp en UTC (localiza si es naive, convierte si ya tiene tz)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        return t.tz_localize("UTC")
    return t.tz_convert("UTC")


# --------------------------------------------------------------------------------------
# Estructuras de datos
# --------------------------------------------------------------------------------------

@dataclass
class Trade:
    """Representa un trade completo."""
    epic: str
    direction: str
    entry_date: Union[datetime, pd.Timestamp]
    exit_date: Union[datetime, pd.Timestamp]
    entry_price: float
    exit_price: float
    units: float
    position_size: float
    pnl: float
    pnl_percent: float
    exit_reason: str
    confidence: float
    duration_hours: float
    day_of_week: str
    hour_of_day: int
    regime: str  # "trending" | "lateral"

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0


@dataclass
class BacktestResults:
    """Resultados completos del backtest."""
    # Capital
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_percent: float
    cagr: float

    # Trades
    trades: List[Trade] = field(default_factory=list)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # P&L
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    profit_factor: float = 0.0

    # Drawdown
    max_drawdown: float = 0.0          # %
    avg_drawdown: float = 0.0          # %
    max_drawdown_duration_days: int = 0
    recovery_time_days: int = 0

    # Riesgo
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    mar_ratio: float = 0.0
    volatility: float = 0.0            # % anualizada

    # Rachas
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Análisis temporal y régimen
    performance_by_day: Dict[str, Dict] = field(default_factory=dict)
    performance_by_hour: Dict[int, Dict] = field(default_factory=dict)
    performance_by_month: Dict[str, Dict] = field(default_factory=dict)
    performance_by_regime: Dict[str, Dict] = field(default_factory=dict)

    # Series
    equity_curve: List[Dict] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_return': self.total_return,
            'total_return_percent': self.total_return_percent,
            'cagr': self.cagr,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'equity_curve': self.equity_curve,
            'trades_detail': [t.__dict__ for t in self.trades],
            'performance_by_regime': self.performance_by_regime,
        }


# --------------------------------------------------------------------------------------
# Motor unificado
# --------------------------------------------------------------------------------------

class BacktestEngine:
    """Motor de backtesting con CapitalTracker, costes, tiempos UTC y régimen."""

    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.strategy = IntradayStrategy()
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []

        # Data y utilidades de la corrida
        self._historical_data: Dict[str, pd.DataFrame] = {}
        self._regimes_map: Dict[str, Dict[pd.Timestamp, str]] = {}  # epic -> {timestamp->regime}
        self._last_costs_df: Optional[pd.DataFrame] = None
        self.report_dir: Optional[Path] = None  # reports/run_<ts>/

        # Asignación (Config con defaults)
        self.use_capital_tracker = bool(getattr(Config, "USE_CAPITAL_TRACKER", True))
        self.capital_tracker = CapitalTracker(
            initial_equity=self.initial_capital,
            daily_budget_pct=float(getattr(Config, "DAILY_BUDGET_PCT", 0.08)),
            per_trade_cap_pct=float(getattr(Config, "PER_TRADE_CAP_PCT", 0.03)),
        )

        # Legacy fallback
        self.legacy_target_pct = float(getattr(Config, "TARGET_PERCENT_OF_AVAILABLE", 0.40))
        self.max_positions = int(getattr(Config, "MAX_POSITIONS", 3))
        self.min_confidence = float(getattr(Config, "MIN_CONFIDENCE", 0.5))

        # SL/TP
        self.sl_buy = float(getattr(Config, "STOP_LOSS_PERCENT_BUY", 0.01))
        self.tp_buy = float(getattr(Config, "TAKE_PROFIT_PERCENT_BUY", 0.02))
        self.sl_sell = float(getattr(Config, "STOP_LOSS_PERCENT_SELL", 0.01))
        self.tp_sell = float(getattr(Config, "TAKE_PROFIT_PERCENT_SELL", 0.02))

    # -------------------------------- API pública --------------------------------

    def run(
        self,
        historical_data: Dict[str, pd.DataFrame],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BacktestResults:
        """Ejecuta el backtest bar-by-bar con fechas y horas reales (UTC)."""
        logger.info("=" * 80)
        logger.info("🔬 BACKTESTING (motor unificado + capital tracker)")
        logger.info("=" * 80)
        logger.info(f"💰 Capital inicial: €{self.initial_capital:,.2f}")
        logger.info(f"⚖️  Asignación: USE_CAPITAL_TRACKER={self.use_capital_tracker} "
                    f"(daily={self.capital_tracker.daily_budget_pct*100:.1f}%, "
                    f"per_trade={self.capital_tracker.per_trade_cap_pct*100:.1f}%)")

        # Report dir bajo reports/
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.report_dir = Path("reports") / f"run_{ts}"
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # Reset de estado
        self.capital = self.initial_capital
        self.trades = []
        self.equity_curve = []
        self._last_costs_df = None
        self._historical_data = {}
        self._regimes_map = {}

        # Normalizar/guardar data input y detectar regímenes por activo
        if not historical_data:
            logger.error("❌ No hay datos históricos")
            return self._create_empty_results()

        for epic, df in historical_data.items():
            df = df.copy()
            # Normalización columnas y tiempos
            if "snapshotTime" in df.columns:
                df["snapshotTime"] = pd.to_datetime(df["snapshotTime"], utc=True, errors="coerce")
            elif "timestamp" in df.columns:
                df["snapshotTime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            else:
                raise ValueError(f"{epic}: falta columna de tiempo (snapshotTime/timestamp)")

            # Columnas OHLC
            rename_map = {}
            if "close" in df.columns and "closePrice" not in df.columns:
                rename_map["close"] = "closePrice"
            if "open" in df.columns and "openPrice" not in df.columns:
                rename_map["open"] = "openPrice"
            if "high" in df.columns and "highPrice" not in df.columns:
                rename_map["high"] = "highPrice"
            if "low" in df.columns and "lowPrice" not in df.columns:
                rename_map["low"] = "lowPrice"
            if rename_map:
                df = df.rename(columns=rename_map)

            # Tipos numéricos
            for col in ["closePrice", "openPrice", "highPrice", "lowPrice", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].apply(lambda x: safe_float(x)), errors="coerce")

            df = df.dropna(subset=["snapshotTime", "closePrice"]).sort_values("snapshotTime").reset_index(drop=True)

            # Día (para loops) y mapa de régimen por timestamp
            df["date"] = df["snapshotTime"].dt.date
            regimes = detect_regime(
                df,
                atr_period=int(getattr(Config, "REGIME_ATR_PERIOD", 14)),
                adx_threshold=float(getattr(Config, "REGIME_ADX_THRESHOLD", 25.0)),
                atr_threshold_pct=float(getattr(Config, "REGIME_ATR_PCT", 0.5)),
            )
            self._regimes_map[epic] = dict(zip(df["snapshotTime"], regimes))
            self._historical_data[epic] = df

        # Rango de días (no horas) para la iteración
        all_dates = self._extract_dates(self._historical_data, start_date, end_date)
        if not all_dates:
            logger.error("❌ No hay fechas válidas en el rango dado")
            return self._create_empty_results()

        logger.info(f"📅 Período: {all_dates[0]} → {all_dates[-1]}  |  Días: {len(all_dates)}")
        logger.info(f"📈 Activos: {', '.join(self._historical_data.keys())}")
        logger.info("-" * 80)

        open_positions: List[Dict] = []

        for i, curr_date in enumerate(all_dates):
            if i % max(len(all_dates) // 10, 1) == 0:
                logger.info(f"⏳ Progreso: {(i / len(all_dates)) * 100:4.0f}%")

            # 1) Actualizar posiciones con última barra del día (timestamp real UTC)
            open_positions = self._update_positions(open_positions, curr_date)

            # 2) Señales (no look-ahead)
            signals = self._get_signals_for_date(curr_date)

            # 3) Aperturas (tracker o legacy), usando el timestamp de la última barra del activo ese día
            if self.use_capital_tracker and signals:
                allocations = self.capital_tracker.allocate_for_signals(
                    equity=self.capital,
                    signals=signals,
                    current_dt=pd.Timestamp(curr_date).to_pydatetime(),
                    allow_partial=True,
                )
                for sig in sorted(signals, key=lambda s: float(s.get("confidence", 0.0)), reverse=True):
                    if len(open_positions) >= self.max_positions:
                        break
                    size_eur = float(allocations.get(sig['epic'], 0.0))
                    if size_eur <= 0 or size_eur > self.capital:
                        continue
                    ts = self._last_bar_timestamp(sig['epic'], curr_date)
                    if ts is None:
                        continue
                    position = self._open_position(sig, ts, override_position_size=size_eur)
                    if position:
                        open_positions.append(position)
                        self.capital_tracker.record_fill(sig['epic'], size_eur, when=ts.to_pydatetime())
            else:
                for sig in signals:
                    if len(open_positions) >= self.max_positions:
                        break
                    if sig['signal'] in ('BUY', 'SELL') and sig['confidence'] >= self.min_confidence:
                        available = self.capital * self.legacy_target_pct
                        position_size = available / max(1, self.max_positions)
                        if position_size > self.capital or position_size <= 0:
                            continue
                        ts = self._last_bar_timestamp(sig['epic'], curr_date)
                        if ts is None:
                            continue
                        position = self._open_position(sig, ts, override_position_size=position_size)
                        if position:
                            open_positions.append(position)

            # 4) Equity del día en timestamp de referencia (última barra del día del primer activo)
            ref_ts = self._reference_timestamp(curr_date)
            equity = self._calculate_equity(open_positions)
            self.equity_curve.append({
                'date': ref_ts if ref_ts is not None else _to_utc(pd.Timestamp(curr_date)),
                'equity': equity,
                'cash': self.capital,
                'open_positions': len(open_positions),
            })

        # Cierre final
        logger.info(f"\n🔚 Cerrando {len(open_positions)} posiciones al finalizar...")
        last_ref = self._reference_timestamp(all_dates[-1]) or _to_utc(pd.Timestamp(all_dates[-1]))
        for p in open_positions:
            self._close_position(p, p['current_price'], last_ref, 'END_OF_BACKTEST')

        # Costes reales (antes de métricas)
        if self.trades:
            logger.info("💰 Aplicando costes reales (comisiones + spread)...")
            df_trades = pd.DataFrame([t.__dict__ for t in self.trades])
            df_trades_net = apply_costs(
                df_trades,
                commission_per_trade=getattr(Config, "COMMISSION_PER_TRADE", 0.0),
                spread_in_points=getattr(Config, "SPREAD_IN_POINTS_DEFAULT", 0.0),
                point_value=getattr(Config, "POINT_VALUE_DEFAULT", 1.0),
                per_instrument_overrides=getattr(Config, "COST_OVERRIDES", None),
            )
            for i, t in enumerate(self.trades):
                t.pnl = float(df_trades_net.loc[i, "pnl_net"])
                if "pnl_percent_net" in df_trades_net.columns:
                    t.pnl_percent = float(df_trades_net.loc[i, "pnl_percent_net"])
            self._last_costs_df = df_trades_net.copy()

        # Métricas
        logger.info("\n📊 Calculando métricas...")
        results = self._calculate_advanced_results()
        return results

    # -------------------------------- Internos --------------------------------

    def _extract_dates(self, data: Dict[str, pd.DataFrame], start_date: Optional[str], end_date: Optional[str]) -> List:
        dates = set()
        for df in data.values():
            dates.update(df["snapshotTime"].dt.date.unique())
        dates = sorted(list(dates))
        if start_date:
            start = pd.to_datetime(start_date).date()
            dates = [d for d in dates if d >= start]
        if end_date:
            end = pd.to_datetime(end_date).date()
            dates = [d for d in dates if d <= end]
        return dates

    def _last_bar_timestamp(self, epic: str, date_) -> Optional[pd.Timestamp]:
        df = self._historical_data.get(epic)
        if df is None:
            return None
        day_data = df[df["snapshotTime"].dt.date == date_]
        if day_data.empty:
            return None
        # FIX: no pasar tz si ya hay tzinfo; normalizar con _to_utc
        val = pd.Timestamp(day_data.iloc[-1]["snapshotTime"])
        return _to_utc(val)

    def _reference_timestamp(self, date_) -> Optional[pd.Timestamp]:
        # Usa el primer activo disponible para tomar el timestamp de equity del día
        for epic in self._historical_data:
            ts = self._last_bar_timestamp(epic, date_)
            if ts is not None:
                return ts
        return None

    def _get_signals_for_date(self, date_) -> List[Dict]:
        signals: List[Dict] = []
        for epic, df in self._historical_data.items():
            subset = df[df["snapshotTime"].dt.date <= date_]
            if len(subset) < getattr(Config, "SMA_LONG", 50):
                continue
            analysis = self.strategy.analyze(subset.copy(), epic)
            # Esperado: {'epic','signal','confidence','current_price',...}
            signals.append(analysis)
        return signals

    def _open_position(self, signal: Dict, ts: pd.Timestamp, *, override_position_size: Optional[float] = None) -> Optional[Dict]:
        price = float(signal['current_price'])
        direction = signal['signal']
        position_size = float(override_position_size) if override_position_size is not None else \
            (self.capital * self.legacy_target_pct) / max(1, self.max_positions)

        if position_size <= 0 or position_size > self.capital:
            return None

        units = position_size / max(price, 1e-12)

        if direction == 'BUY':
            stop_loss = price * (1 - self.sl_buy)
            take_profit = price * (1 + self.tp_buy)
        else:
            stop_loss = price * (1 + self.sl_sell)
            take_profit = price * (1 - self.tp_sell)

        self.capital -= position_size

        return {
            'epic': signal['epic'],
            'direction': direction,
            'entry_price': price,
            'entry_date': _to_utc(ts),  # timestamp real UTC
            'units': units,
            'position_size': position_size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'current_price': price,
            'confidence': float(signal.get('confidence', 0.0)),
        }

    def _update_positions(self, positions: List[Dict], date_) -> List[Dict]:
        updated = []
        for position in positions:
            epic = position['epic']
            df = self._historical_data.get(epic)
            if df is None:
                updated.append(position); continue

            day_data = df[df["snapshotTime"].dt.date == date_]
            if day_data.empty:
                updated.append(position); continue

            row = day_data.iloc[-1]
            current_price = safe_float(row['closePrice'])
            ts = _to_utc(pd.Timestamp(row['snapshotTime']))
            position['current_price'] = current_price

            closed = False
            if position['direction'] == 'BUY':
                if current_price <= position['stop_loss']:
                    self._close_position(position, position['stop_loss'], ts, 'STOP_LOSS'); closed = True
                elif current_price >= position['take_profit']:
                    self._close_position(position, position['take_profit'], ts, 'TAKE_PROFIT'); closed = True
            else:
                if current_price >= position['stop_loss']:
                    self._close_position(position, position['stop_loss'], ts, 'STOP_LOSS'); closed = True
                elif current_price <= position['take_profit']:
                    self._close_position(position, position['take_profit'], ts, 'TAKE_PROFIT'); closed = True

            if not closed:
                updated.append(position)
        return updated

    def _lookup_regime(self, epic: str, ts: pd.Timestamp) -> str:
        m = self._regimes_map.get(epic, {})
        if ts in m:
            return m[ts]
        keys = sorted(m.keys())
        for k in reversed(keys):
            if k <= ts:
                return m[k]
        return "lateral"

    def _close_position(self, position: Dict, exit_price: float, exit_ts: pd.Timestamp, reason: str):
        entry_price = position['entry_price']
        units = position['units']
        direction = position['direction']
        entry_ts = _to_utc(position['entry_date'])
        exit_ts = _to_utc(exit_ts)

        pnl = (exit_price - entry_price) * units if direction == 'BUY' else (entry_price - exit_price) * units
        self.capital += position['position_size'] + pnl

        duration_hours = float((exit_ts - entry_ts).total_seconds() / 3600.0)
        day_of_week = exit_ts.strftime('%A')
        hour_of_day = int(exit_ts.hour)
        regime = self._lookup_regime(position['epic'], exit_ts)

        trade = Trade(
            epic=position['epic'],
            direction=direction,
            entry_date=entry_ts.to_pydatetime(),
            exit_date=exit_ts.to_pydatetime(),
            entry_price=float(entry_price),
            exit_price=float(exit_price),
            units=float(units),
            position_size=float(position['position_size']),
            pnl=float(pnl),
            pnl_percent=(float(pnl) / max(float(position['position_size']), 1e-12)) * 100,
            exit_reason=reason,
            confidence=float(position.get('confidence', 0.0)),
            duration_hours=duration_hours,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            regime=regime,
        )
        self.trades.append(trade)

    def _calculate_equity(self, open_positions: List[Dict]) -> float:
        total = self.capital
        for p in open_positions:
            pnl = (p['current_price'] - p['entry_price']) * p['units'] if p['direction'] == 'BUY' \
                  else (p['entry_price'] - p['current_price']) * p['units']
            total += p['position_size'] + pnl
        return float(total)

    # -------------------------------- Métricas --------------------------------

    def _calculate_advanced_results(self) -> BacktestResults:
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['date'] = pd.to_datetime(equity_df['date'], utc=True)
        equity_df = equity_df.set_index('date').sort_index()
        equity_df['returns'] = equity_df['equity'].pct_change()
        daily_returns = equity_df['returns'].dropna().tolist()

        total_return = self.capital - self.initial_capital
        total_return_percent = (total_return / self.initial_capital) * 100
        days = max((equity_df.index[-1] - equity_df.index[0]).days, 1)
        years = max(days / 365.25, 1e-12)
        cagr = ((self.capital / self.initial_capital) ** (1 / years) - 1) * 100

        dd_stats = self._drawdown_stats(equity_df)
        risk_metrics = self._risk_metrics(daily_returns, cagr, dd_stats['max_drawdown'])
        trade_stats = self._trade_stats()
        temporal_stats = self._temporal_analysis()
        regime_stats = self._regime_analysis()

        return BacktestResults(
            initial_capital=float(self.initial_capital),
            final_capital=float(self.capital),
            total_return=float(total_return),
            total_return_percent=float(total_return_percent),
            cagr=float(cagr),
            trades=self.trades,
            equity_curve=self.equity_curve,
            daily_returns=daily_returns,
            **trade_stats,
            **dd_stats,
            **risk_metrics,
            **temporal_stats,
            performance_by_regime=regime_stats,
        )

    def _drawdown_stats(self, equity_df: pd.DataFrame) -> Dict:
        if equity_df.empty:
            return {'max_drawdown': 0.0, 'avg_drawdown': 0.0, 'max_drawdown_duration_days': 0, 'recovery_time_days': 0}

        eq = equity_df['equity']
        running_max = eq.cummax()
        dd = (eq - running_max) / running_max * 100
        max_dd = float(dd.min()) if not dd.empty else 0.0
        avg_dd = float(dd[dd < 0].mean()) if (dd < 0).any() else 0.0

        dd_duration = 0
        in_dd = False
        start = None
        for date, v in dd.items():
            if v < -1 and not in_dd:
                in_dd = True; start = date
            elif v >= 0 and in_dd:
                if start is not None:
                    dd_duration = max(dd_duration, (date - start).days)
                in_dd = False; start = None

        return {
            'max_drawdown': abs(max_dd),
            'avg_drawdown': abs(avg_dd),
            'max_drawdown_duration_days': dd_duration,
            'recovery_time_days': dd_duration,
        }

    def _risk_metrics(self, daily_returns: List[float], cagr: float, max_dd: float) -> Dict:
        if not daily_returns or len(daily_returns) < 2:
            return dict(sharpe_ratio=0.0, sortino_ratio=0.0, calmar_ratio=0.0, mar_ratio=0.0, volatility=0.0)

        arr = np.array(daily_returns, dtype=float)
        vol = float(np.std(arr, ddof=1) * np.sqrt(252) * 100)

        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1))
        sharpe = (mean / std) * np.sqrt(252) if std > 0 else 0.0

        downside = arr[arr < 0]
        dstd = float(np.std(downside, ddof=1)) if downside.size else std
        sortino = (mean / dstd) * np.sqrt(252) if dstd > 0 else 0.0

        calmar = (cagr / max_dd) if max_dd > 0 else 0.0
        mar = calmar

        return {
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'mar_ratio': mar,
            'volatility': vol,
        }

    def _trade_stats(self) -> Dict:
        if not self.trades:
            return {
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0, 'win_rate': 0.0,
                'avg_win': 0.0, 'avg_loss': 0.0, 'largest_win': 0.0, 'largest_loss': 0.0,
                'profit_factor': 0.0, 'max_consecutive_wins': 0, 'max_consecutive_losses': 0
            }

        winners = [t for t in self.trades if t.is_winner]
        losers = [t for t in self.trades if not t.is_winner]

        total_wins = sum(t.pnl for t in winners)
        total_losses = abs(sum(t.pnl for t in losers))

        # Rachas
        max_w, max_l = 0, 0
        cur_w, cur_l = 0, 0
        for t in self.trades:
            if t.is_winner:
                cur_w += 1; cur_l = 0; max_w = max(max_w, cur_w)
            else:
                cur_l += 1; cur_w = 0; max_l = max(max_l, cur_l)

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'win_rate': (len(winners) / max(len(self.trades), 1)) * 100.0,
            'avg_win': float(np.mean([t.pnl for t in winners])) if winners else 0.0,
            'avg_loss': float(np.mean([t.pnl for t in losers])) if losers else 0.0,
            'largest_win': max([t.pnl for t in winners]) if winners else 0.0,
            'largest_loss': min([t.pnl for t in losers]) if losers else 0.0,
            'profit_factor': (total_wins / total_losses) if total_losses > 0 else float('inf'),
            'max_consecutive_wins': max_w,
            'max_consecutive_losses': max_l,
        }

    def _temporal_analysis(self) -> Dict:
        if not self.trades:
            return {'performance_by_day': {}, 'performance_by_hour': {}, 'performance_by_month': {}}

        # Día de la semana
        by_day: Dict[str, Dict] = {}
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            dtrades = [t for t in self.trades if t.day_of_week == day]
            if dtrades:
                winners = [t for t in dtrades if t.is_winner]
                by_day[day] = {
                    'total_trades': len(dtrades),
                    'win_rate': (len(winners) / len(dtrades)) * 100.0,
                    'total_pnl': float(sum(t.pnl for t in dtrades)),
                    'avg_pnl': float(np.mean([t.pnl for t in dtrades])),
                }

        # Hora UTC (buckets EU/US)
        buckets = {'morning': [], 'afternoon': [], 'evening': []}
        for t in self.trades:
            if 7 <= t.hour_of_day < 12:
                buckets['morning'].append(t)
            elif 12 <= t.hour_of_day < 18:
                buckets['afternoon'].append(t)
            else:
                buckets['evening'].append(t)

        by_hour: Dict[str, Dict] = {}
        for k, lst in buckets.items():
            if lst:
                winners = [t for t in lst if t.is_winner]
                by_hour[k] = {
                    'total_trades': len(lst),
                    'win_rate': (len(winners) / len(lst)) * 100.0,
                    'total_pnl': float(sum(t.pnl for t in lst)),
                    'avg_pnl': float(np.mean([t.pnl for t in lst])),
                }

        return {'performance_by_day': by_day, 'performance_by_hour': by_hour, 'performance_by_month': {}}

    def _regime_analysis(self) -> Dict:
        if not self.trades:
            return {}
        out: Dict[str, Dict] = {}
        for regime in ("trending", "lateral"):
            lst = [t for t in self.trades if t.regime == regime]
            if not lst:
                continue
            winners = [t for t in lst if t.is_winner]
            gains = sum(t.pnl for t in lst if t.pnl > 0)
            losses = abs(sum(t.pnl for t in lst if t.pnl < 0))
            out[regime] = {
                'total_trades': len(lst),
                'win_rate': (len(winners) / len(lst)) * 100.0,
                'profit_factor': (gains / losses) if losses > 0 else float('inf'),
                'total_pnl': float(sum(t.pnl for t in lst)),
                'avg_pnl': float(np.mean([t.pnl for t in lst])),
            }
        return out

    def _create_empty_results(self) -> BacktestResults:
        return BacktestResults(
            initial_capital=float(self.initial_capital),
            final_capital=float(self.initial_capital),
            total_return=0.0,
            total_return_percent=0.0,
            cagr=0.0,
        )


# --------------------------------------------------------------------------------------
# Export helpers (guardar en reports/run_<ts>/ por defecto)
# --------------------------------------------------------------------------------------

from typing import Union as _Union  # evitar colisión de nombre arriba
_last_report_dir: Optional[Path] = None  # fallback si se llama fuera del engine


def _resolve_out_path(default_name: str, report_dir: Optional[_Union[str, Path]]) -> Path:
    if report_dir is not None:
        rd = Path(report_dir); rd.mkdir(parents=True, exist_ok=True); return rd / default_name
    if _last_report_dir and _last_report_dir.exists():
        return _last_report_dir / default_name
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rd = Path("reports") / f"run_{ts}"
    rd.mkdir(parents=True, exist_ok=True)
    return rd / default_name


def export_results_to_csv(results: BacktestResults | Dict, filename: str = 'trades.csv', *, report_dir: Optional[_Union[str, Path]] = None) -> Path:
    """
    Exporta trades a CSV. Si no se especifica report_dir, guarda en reports/run_<ts>/.
    Devuelve la ruta escrita.
    """
    global _last_report_dir
    out_path = _resolve_out_path(filename, report_dir)

    # Extraer trades homogéneos
    if isinstance(results, BacktestResults):
        trades = results.trades
    else:
        details = results.get('trades_detail', [])
        trades = []
        for d in details:
            trades.append(Trade(
                epic=d.get('epic', ''),
                direction=d.get('direction', ''),
                entry_date=pd.Timestamp(d.get('entry_date')).to_pydatetime(),
                exit_date=pd.Timestamp(d.get('exit_date')).to_pydatetime(),
                entry_price=float(d.get('entry_price', 0.0)),
                exit_price=float(d.get('exit_price', 0.0)),
                units=float(d.get('units', 0.0)),
                position_size=float(d.get('position_size', 0.0)),
                pnl=float(d.get('pnl', 0.0)),
                pnl_percent=float(d.get('pnl_percent', 0.0)),
                exit_reason=d.get('reason', d.get('exit_reason', '')),
                confidence=float(d.get('confidence', 0.0)),
                duration_hours=float(d.get('duration_hours', 0.0)),
                day_of_week=str(d.get('day_of_week', '')),
                hour_of_day=int(d.get('hour_of_day', 12)),
                regime=str(d.get('regime', 'lateral')),
            ))

    if not trades:
        logger.warning("No hay trades para exportar")
        return out_path

    rows = []
    for t in trades:
        rows.append({
            'epic': t.epic,
            'direction': t.direction,
            'entry_date': t.entry_date,
            'exit_date': t.exit_date,
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'units': t.units,
            'position_size': t.position_size,
            'pnl': t.pnl,
            'pnl_percent': t.pnl_percent,
            'exit_reason': t.exit_reason,
            'confidence': t.confidence,
            'duration_hours': t.duration_hours,
            'day_of_week': t.day_of_week,
            'hour_of_day': t.hour_of_day,
            'regime': t.regime,
        })
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    logger.info(f"✅ Trades exportados a {out_path.as_posix()}")

    _last_report_dir = out_path.parent
    return out_path


def export_summary_to_json(results: BacktestResults | Dict, filename: str = 'metrics.json', *, report_dir: Optional[_Union[str, Path]] = None) -> Path:
    """
    Exporta un resumen a JSON (compatible con BacktestResults o dict legacy).
    Si no se especifica report_dir, guarda en reports/run_<ts>/.
    Devuelve la ruta escrita.
    """
    import json
    global _last_report_dir
    out_path = _resolve_out_path(filename, report_dir)

    if isinstance(results, BacktestResults):
        summary = {
            'capital': {
                'initial': results.initial_capital,
                'final': results.final_capital,
                'total_return': results.total_return,
                'total_return_percent': results.total_return_percent,
                'cagr': results.cagr,
            },
            'trades': {
                'total': results.total_trades,
                'winning': results.winning_trades,
                'losing': results.losing_trades,
                'win_rate': results.win_rate,
                'profit_factor': results.profit_factor,
            },
            'risk': {
                'max_drawdown': results.max_drawdown,
                'sharpe_ratio': results.sharpe_ratio,
                'sortino_ratio': results.sortino_ratio,
                'calmar_ratio': results.calmar_ratio,
                'volatility': results.volatility,
            },
            'temporal': {
                'by_day': results.performance_by_day,
                'by_hour': results.performance_by_hour,
                'by_regime': results.performance_by_regime,
            },
        }
    else:
        summary = {
            'capital': {
                'initial': results.get('initial_capital', 0.0),
                'final': results.get('final_capital', 0.0),
                'total_return': results.get('total_return', 0.0),
                'total_return_percent': results.get('total_return_percent', 0.0),
                'cagr': results.get('cagr', 0.0),
            },
            'trades': {
                'total': results.get('total_trades', 0),
                'winning': results.get('winning_trades', 0),
                'losing': results.get('losing_trades', 0),
                'win_rate': results.get('win_rate', 0.0),
                'profit_factor': results.get('profit_factor', 0.0),
            },
            'risk': {
                'max_drawdown': results.get('max_drawdown', 0.0),
                'sharpe_ratio': results.get('sharpe_ratio', 0.0),
                'sortino_ratio': results.get('sortino_ratio', 0.0),
                'calmar_ratio': results.get('calmar_ratio', 0.0),
                'volatility': results.get('volatility', 0.0),
            },
            'temporal': results.get('temporal', {}),
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"✅ Resumen exportado a {out_path.as_posix()}")
    _last_report_dir = out_path.parent
    return out_path
