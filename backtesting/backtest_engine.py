"""
backtesting/backtest_engine.py

Motor de Backtesting UNIFICADO (avanzado) para el proyecto.
- Reemplaza la versión base y la avanzada anterior.
- Mantiene el nombre de clase `BacktestEngine` para NO romper imports existentes.
- Incluye métricas ampliadas, equity curve, análisis temporal y funciones de exportación.

Uso típico:
    engine = BacktestEngine(initial_capital=10000.0)
    results = engine.run(historical_data, start_date="2024-01-01", end_date="2024-12-31")
    export_results_to_csv(results, "trades.csv")
    export_summary_to_json(results, "summary.json")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from strategies.intraday_strategy import IntradayStrategy
from config import Config
from utils.helpers import safe_float

logger = logging.getLogger(__name__)


# =========================
# Data structures
# =========================

@dataclass
class Trade:
    """Representa un trade completo."""
    epic: str
    direction: str
    entry_date: datetime
    exit_date: datetime
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

    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    mar_ratio: float = 0.0
    volatility: float = 0.0            # % anualizada

    # Rachas
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Análisis temporal
    performance_by_day: Dict[str, Dict] = field(default_factory=dict)
    performance_by_hour: Dict[int, Dict] = field(default_factory=dict)
    performance_by_month: Dict[str, Dict] = field(default_factory=dict)

    # Series
    equity_curve: List[Dict] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)

    # Compatibilidad: conversión simple a dict
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
        }


# =========================
# Unified Backtest Engine
# =========================

class BacktestEngine:
    """Motor de backtesting avanzado unificado."""

    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.strategy = IntradayStrategy()
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []

    # ---------- Public API ----------

    def run(
        self,
        historical_data: Dict[str, pd.DataFrame],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BacktestResults:
        """
        Ejecuta backtest avanzado (día a día, sin look-ahead).

        Args:
            historical_data: {epic: DataFrame con precios. columnas esperadas:
                             snapshotTime|timestamp y closePrice (numérico)}
            start_date: 'YYYY-MM-DD' (opcional)
            end_date: 'YYYY-MM-DD' (opcional)
        """
        logger.info("=" * 80)
        logger.info("🔬 BACKTESTING (motor unificado)")
        logger.info("=" * 80)
        logger.info(f"💰 Capital inicial: €{self.initial_capital:,.2f}")

        # Reset
        self.capital = self.initial_capital
        self.trades = []
        self.equity_curve = []
        open_positions: List[Dict] = []

        if not historical_data:
            logger.error("❌ No hay datos históricos")
            return self._create_empty_results()

        # Fechas únicas (ordenadas) y filtradas
        all_dates = self._extract_dates(historical_data, start_date, end_date)
        if not all_dates:
            logger.error("❌ No hay fechas válidas en el rango dado")
            return self._create_empty_results()

        logger.info(f"📅 Período: {all_dates[0]} → {all_dates[-1]}  |  Días: {len(all_dates)}")
        logger.info(f"📈 Activos: {', '.join(historical_data.keys())}")
        logger.info("-" * 80)

        # Simulación día a día
        for i, current_date in enumerate(all_dates):
            if i % max(len(all_dates) // 10, 1) == 0:
                logger.info(f"⏳ Progreso: {(i / len(all_dates)) * 100:4.0f}%")

            # 1) Actualizar posiciones abiertas (SL/TP)
            open_positions = self._update_positions(open_positions, historical_data, current_date)

            # 2) Generar señales (sin mirar el futuro)
            signals = self._get_signals_for_date(historical_data, current_date)

            # 3) Aperturas nuevas
            for signal in signals:
                if len(open_positions) >= Config.MAX_POSITIONS:
                    break
                if signal['signal'] in ('BUY', 'SELL') and signal['confidence'] >= Config.MIN_CONFIDENCE:
                    position = self._open_position(signal, current_date)
                    if position:
                        open_positions.append(position)

            # 4) Equity del día
            equity = self._calculate_equity(open_positions)
            self.equity_curve.append({
                'date': current_date,
                'equity': equity,
                'cash': self.capital,
                'open_positions': len(open_positions),
            })

        # Cierre final de posiciones pendientes
        logger.info(f"\n🔚 Cerrando {len(open_positions)} posiciones al finalizar...")
        for position in open_positions:
            self._close_position(position, position['current_price'], all_dates[-1], 'END_OF_BACKTEST')

        # Métricas avanzadas
        logger.info("\n📊 Calculando métricas...")
        results = self._calculate_advanced_results(all_dates)

        self._print_results(results)
        return results

    # ---------- Internals ----------

    def _extract_dates(
        self,
        historical_data: Dict[str, pd.DataFrame],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List:
        dates = set()
        for df in historical_data.values():
            if 'snapshotTime' in df.columns:
                dates.update(pd.to_datetime(df['snapshotTime']).dt.date)
            elif 'timestamp' in df.columns:
                dates.update(pd.to_datetime(df['timestamp']).dt.date)
        dates = sorted(list(dates))
        if start_date:
            start = pd.to_datetime(start_date).date()
            dates = [d for d in dates if d >= start]
        if end_date:
            end = pd.to_datetime(end_date).date()
            dates = [d for d in dates if d <= end]
        return dates

    def _get_signals_for_date(self, historical_data: Dict[str, pd.DataFrame], date) -> List[Dict]:
        signals = []
        for epic, df in historical_data.items():
            if 'snapshotTime' in df.columns:
                df['date'] = pd.to_datetime(df['snapshotTime']).dt.date
            elif 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp']).dt.date
            else:
                continue

            subset = df[df['date'] <= date].copy()
            if len(subset) < Config.SMA_LONG:
                continue

            analysis = self.strategy.analyze(subset, epic)
            signals.append(analysis)
        return signals

    def _open_position(self, signal: Dict, date) -> Optional[Dict]:
        price = signal['current_price']
        direction = signal['signal']

        # Tamaño de posición
        available = self.capital * Config.TARGET_PERCENT_OF_AVAILABLE
        position_size = available / max(1, Config.MAX_POSITIONS)
        if position_size <= 0 or position_size > self.capital:
            return None

        units = position_size / max(price, 1e-12)

        if direction == 'BUY':
            stop_loss = price * (1 - Config.STOP_LOSS_PERCENT_BUY)
            take_profit = price * (1 + Config.TAKE_PROFIT_PERCENT_BUY)
        else:
            stop_loss = price * (1 + Config.STOP_LOSS_PERCENT_SELL)
            take_profit = price * (1 - Config.TAKE_PROFIT_PERCENT_SELL)

        self.capital -= position_size

        return {
            'epic': signal['epic'],
            'direction': direction,
            'entry_price': price,
            'entry_date': date,
            'units': units,
            'position_size': position_size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'current_price': price,
            'confidence': signal['confidence'],
        }

    def _update_positions(self, positions: List[Dict], historical_data: Dict, date) -> List[Dict]:
        updated = []
        for position in positions:
            epic = position['epic']
            if epic not in historical_data:
                updated.append(position)
                continue

            df = historical_data[epic]
            if 'snapshotTime' in df.columns:
                df['date'] = pd.to_datetime(df['snapshotTime']).dt.date
            elif 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp']).dt.date

            day_data = df[df['date'] == date]
            if day_data.empty:
                updated.append(position)
                continue

            current_price = safe_float(day_data.iloc[-1]['closePrice'])
            position['current_price'] = current_price

            closed = False
            if position['direction'] == 'BUY':
                if current_price <= position['stop_loss']:
                    self._close_position(position, position['stop_loss'], date, 'STOP_LOSS')
                    closed = True
                elif current_price >= position['take_profit']:
                    self._close_position(position, position['take_profit'], date, 'TAKE_PROFIT')
                    closed = True
            else:
                if current_price >= position['stop_loss']:
                    self._close_position(position, position['stop_loss'], date, 'STOP_LOSS')
                    closed = True
                elif current_price <= position['take_profit']:
                    self._close_position(position, position['take_profit'], date, 'TAKE_PROFIT')
                    closed = True

            if not closed:
                updated.append(position)

        return updated

    def _close_position(self, position: Dict, exit_price: float, exit_date, reason: str):
        entry_price = position['entry_price']
        units = position['units']
        direction = position['direction']
        entry_date = position['entry_date']

        pnl = (exit_price - entry_price) * units if direction == 'BUY' else (entry_price - exit_price) * units
        self.capital += position['position_size'] + pnl

        # Duración y timestamp info
        if isinstance(entry_date, datetime):
            duration_hours = (exit_date - entry_date).total_seconds() / 3600
        else:
            duration_hours = (exit_date - entry_date).days * 24

        exit_dt = pd.to_datetime(exit_date)
        day_of_week = exit_dt.strftime('%A')
        hour_of_day = getattr(exit_dt, 'hour', 12)

        trade = Trade(
            epic=position['epic'],
            direction=direction,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            units=units,
            position_size=position['position_size'],
            pnl=pnl,
            pnl_percent=(pnl / max(position['position_size'], 1e-12)) * 100,
            exit_reason=reason,
            confidence=position['confidence'],
            duration_hours=duration_hours,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
        )
        self.trades.append(trade)

    def _calculate_equity(self, open_positions: List[Dict]) -> float:
        total = self.capital
        for p in open_positions:
            pnl = (p['current_price'] - p['entry_price']) * p['units'] if p['direction'] == 'BUY' \
                  else (p['entry_price'] - p['current_price']) * p['units']
            total += p['position_size'] + pnl
        return total

    # ---------- Metrics ----------

    def _calculate_advanced_results(self, all_dates: List) -> BacktestResults:
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        equity_df = equity_df.set_index('date')
        equity_df['returns'] = equity_df['equity'].pct_change()
        daily_returns = equity_df['returns'].dropna().tolist()

        total_return = self.capital - self.initial_capital
        total_return_percent = (total_return / self.initial_capital) * 100
        years = max(len(all_dates) / 365.25, 1e-12)
        cagr = ((self.capital / self.initial_capital) ** (1 / years) - 1) * 100

        dd_stats = self._drawdown_stats(equity_df)
        risk_metrics = self._risk_metrics(daily_returns, cagr, dd_stats['max_drawdown'])
        trade_stats = self._trade_stats()
        temporal_stats = self._temporal_analysis()

        return BacktestResults(
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            total_return=total_return,
            total_return_percent=total_return_percent,
            cagr=cagr,
            trades=self.trades,
            equity_curve=self.equity_curve,
            daily_returns=daily_returns,
            **trade_stats,
            **dd_stats,
            **risk_metrics,
            **temporal_stats,
        )

    def _drawdown_stats(self, equity_df: pd.DataFrame) -> Dict:
        eq = equity_df['equity']
        running_max = eq.expanding().max()
        dd = (eq - running_max) / running_max * 100
        max_dd = float(dd.min()) if not dd.empty else 0.0
        avg_dd = float(dd[dd < 0].mean()) if (dd < 0).any() else 0.0

        # Duración del peor DD (simple)
        dd_duration = 0
        in_dd = False
        start = None
        for date, v in dd.items():
            if v < -1 and not in_dd:
                in_dd = True
                start = date
            elif v >= 0 and in_dd:
                if start is not None:
                    dd_duration = max(dd_duration, (date - start).days)
                in_dd = False
                start = None

        return {
            'max_drawdown': abs(max_dd),
            'avg_drawdown': abs(avg_dd),
            'max_drawdown_duration_days': dd_duration,
            'recovery_time_days': dd_duration,  # aproximación
        }

    def _risk_metrics(self, daily_returns: List[float], cagr: float, max_dd: float) -> Dict:
        if not daily_returns or len(daily_returns) < 2:
            return dict(sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0, mar_ratio=0, volatility=0)

        arr = np.array(daily_returns)
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
                cur_w += 1; cur_l = 0
                max_w = max(max_w, cur_w)
            else:
                cur_l += 1; cur_w = 0
                max_l = max(max_l, cur_l)

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
            return {
                'performance_by_day': {},
                'performance_by_hour': {},
                'performance_by_month': {},
            }

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

        # Hora (bucket simple)
        buckets = {'morning': [], 'afternoon': [], 'evening': []}
        for t in self.trades:
            if 9 <= t.hour_of_day < 13:
                buckets['morning'].append(t)
            elif 13 <= t.hour_of_day < 18:
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

        return {
            'performance_by_day': by_day,
            'performance_by_hour': by_hour,
            'performance_by_month': {},  # opcional
        }

    def _create_empty_results(self) -> BacktestResults:
        return BacktestResults(
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
            total_return=0.0,
            total_return_percent=0.0,
            cagr=0.0,
        )

    # ---------- Logging ----------

    def _print_results(self, r: BacktestResults):
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESULTADOS")
        logger.info("=" * 80)

        logger.info("\n💰 CAPITAL")
        logger.info("-" * 80)
        logger.info(f"Inicial:     €{r.initial_capital:,.2f}")
        logger.info(f"Final:       €{r.final_capital:,.2f}")
        logger.info(f"Retorno:     €{r.total_return:,.2f} ({r.total_return_percent:.2f}%)")
        logger.info(f"CAGR:        {r.cagr:.2f}%")

        logger.info("\n📈 TRADING")
        logger.info("-" * 80)
        logger.info(f"Trades:      {r.total_trades}  |  Win: {r.winning_trades}  |  Loss: {r.losing_trades}")
        logger.info(f"Win rate:    {r.win_rate:.1f}%  |  PF: {r.profit_factor:.2f}")
        logger.info(f"Avg Win:     €{r.avg_win:.2f}  |  Avg Loss: €{r.avg_loss:.2f}")
        logger.info(f"Max Win:     €{r.largest_win:.2f}  |  Max Loss: €{r.largest_loss:.2f}")
        logger.info(f"Rachas  W/L: {r.max_consecutive_wins}/{r.max_consecutive_losses}")

        logger.info("\n📉 RIESGO")
        logger.info("-" * 80)
        logger.info(f"Max DD:      {r.max_drawdown:.2f}%  |  Avg DD: {r.avg_drawdown:.2f}%")
        logger.info(f"Recuperación: {r.recovery_time_days} días")
        logger.info(f"Sharpe:      {r.sharpe_ratio:.3f}  |  Sortino: {r.sortino_ratio:.3f}")
        logger.info(f"Calmar:      {r.calmar_ratio:.3f}  |  Vol (ann): {r.volatility:.2f}%")

        if r.performance_by_day:
            logger.info("\n📅 Por día de la semana")
            logger.info("-" * 80)
            for day, s in r.performance_by_day.items():
                logger.info(f"{day:10} | Trades: {s['total_trades']:3} | Win: {s['win_rate']:5.1f}% | PnL: €{s['total_pnl']:+.2f}")

        if r.performance_by_hour:
            logger.info("\n🕒 Por período del día")
            logger.info("-" * 80)
            for k, s in r.performance_by_hour.items():
                logger.info(f"{k.capitalize():10} | Trades: {s['total_trades']:3} | Win: {s['win_rate']:5.1f}% | PnL: €{s['total_pnl']:+.2f}")

        logger.info("\n" + "=" * 80)


# =========================
# Export helpers
# =========================

def export_results_to_csv(results: BacktestResults | Dict, filename: str = 'backtest_results.csv'):
    """
    Exporta trades a CSV. Acepta BacktestResults o dict legacy con 'trades_detail'.
    """
    if isinstance(results, BacktestResults):
        trades = results.trades
    else:
        # compatibilidad con versiones antiguas
        details = results.get('trades_detail', [])
        if not details:
            logger.warning("No hay trades para exportar")
            return
        # Convertir dicts a objetos homogéneos:
        trades = []
        for d in details:
            trades.append(Trade(
                epic=d.get('epic', ''),
                direction=d.get('direction', ''),
                entry_date=d.get('entry_date'),
                exit_date=d.get('exit_date'),
                entry_price=d.get('entry_price', 0.0),
                exit_price=d.get('exit_price', 0.0),
                units=d.get('units', 0.0),
                position_size=d.get('position_size', 0.0),
                pnl=d.get('pnl', 0.0),
                pnl_percent=d.get('pnl_percent', 0.0),
                exit_reason=d.get('reason', d.get('exit_reason', '')),
                confidence=d.get('confidence', 0.0),
                duration_hours=float(d.get('duration_hours', 0.0)),
                day_of_week=str(d.get('day_of_week', '')),
                hour_of_day=int(d.get('hour_of_day', 12)),
            ))

    if not trades:
        logger.warning("No hay trades para exportar")
        return

    rows = []
    for t in trades:
        rows.append({
            'epic': t.epic,
            'direction': t.direction,
            'entry_date': t.entry_date,
            'exit_date': t.exit_date,
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'position_size': t.position_size,
            'pnl': t.pnl,
            'pnl_percent': t.pnl_percent,
            'exit_reason': t.exit_reason,
            'confidence': t.confidence,
            'duration_hours': t.duration_hours,
            'day_of_week': t.day_of_week,
        })

    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False)
    logger.info(f"✅ Trades exportados a {filename}")


def export_summary_to_json(results: BacktestResults | Dict, filename: str = 'backtest_summary.json'):
    """Exporta un resumen a JSON (compatible con BacktestResults o dict legacy)."""
    import json

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
            },
        }
    else:
        # Fallback para dicts antiguos
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

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"✅ Resumen exportado a {filename}")
