"""
Motor de Backtesting Avanzado - Análisis exhaustivo con múltiples métricas
Incluye: Sharpe ratio, Calmar ratio, análisis temporal, régimen de mercado
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from strategies.intraday_strategy import IntradayStrategy
from config import Config
from utils.helpers import safe_float

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Representa un trade completo"""
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
    """Resultados completos del backtest"""
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
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    recovery_time_days: int = 0
    
    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    mar_ratio: float = 0.0
    volatility: float = 0.0
    
    # Consecutive
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Temporal analysis
    performance_by_day: Dict[str, Dict] = field(default_factory=dict)
    performance_by_hour: Dict[int, Dict] = field(default_factory=dict)
    performance_by_month: Dict[str, Dict] = field(default_factory=dict)
    
    # Market regime
    performance_in_trend: Dict = field(default_factory=dict)
    performance_in_lateral: Dict = field(default_factory=dict)
    performance_by_volatility: Dict[str, Dict] = field(default_factory=dict)
    
    # Equity curve
    equity_curve: List[Dict] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)


class AdvancedBacktestEngine:
    """Motor de backtesting avanzado con análisis exhaustivo"""
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.strategy = IntradayStrategy()
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        
    def run(
        self, 
        historical_data: Dict[str, pd.DataFrame],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> BacktestResults:
        """
        Ejecuta backtest exhaustivo
        
        Args:
            historical_data: {epic: DataFrame con precio histórico}
            start_date: Fecha inicio (opcional)
            end_date: Fecha fin (opcional)
            
        Returns:
            BacktestResults con todas las métricas
        """
        logger.info("="*80)
        logger.info("🔬 BACKTESTING EXHAUSTIVO - ANÁLISIS AVANZADO")
        logger.info("="*80)
        logger.info(f"💰 Capital inicial: €{self.initial_capital:,.2f}")
        
        # Reset
        self.capital = self.initial_capital
        self.trades = []
        self.equity_curve = []
        open_positions: List[Dict] = []
        
        # Validar datos
        if not historical_data:
            logger.error("❌ No hay datos históricos")
            return self._create_empty_results()
        
        # Preparar fechas
        all_dates = self._extract_dates(historical_data, start_date, end_date)
        
        if len(all_dates) < 30:
            logger.warning(f"⚠️  Solo {len(all_dates)} días de datos (mínimo recomendado: 180)")
        
        logger.info(f"📅 Período: {all_dates[0]} a {all_dates[-1]}")
        logger.info(f"📊 Total días: {len(all_dates)}")
        logger.info(f"📈 Activos: {', '.join(historical_data.keys())}")
        logger.info("-"*80)
        
        # Simular trading día por día
        for i, current_date in enumerate(all_dates):
            # Progreso cada 10%
            if i % max(len(all_dates) // 10, 1) == 0:
                progress = (i / len(all_dates)) * 100
                logger.info(f"⏳ Progreso: {progress:.0f}% ({i}/{len(all_dates)} días)")
            
            # Actualizar posiciones (verificar SL/TP)
            open_positions = self._update_positions(
                open_positions, 
                historical_data, 
                current_date
            )
            
            # Buscar nuevas señales
            signals = self._get_signals_for_date(historical_data, current_date)
            
            # Abrir nuevas posiciones
            for signal in signals:
                if len(open_positions) >= Config.MAX_POSITIONS:
                    break
                
                if signal['signal'] in ['BUY', 'SELL'] and \
                   signal['confidence'] >= Config.MIN_CONFIDENCE:
                    position = self._open_position(signal, current_date)
                    if position:
                        open_positions.append(position)
            
            # Registrar equity
            equity = self._calculate_equity(open_positions, historical_data, current_date)
            self.equity_curve.append({
                'date': current_date,
                'equity': equity,
                'cash': self.capital,
                'open_positions': len(open_positions)
            })
        
        # Cerrar posiciones al final
        logger.info(f"\n🔚 Cerrando {len(open_positions)} posiciones abiertas...")
        for position in open_positions:
            self._close_position(
                position, 
                position['current_price'], 
                all_dates[-1], 
                'END_OF_BACKTEST'
            )
        
        # Calcular resultados completos
        logger.info("\n📊 Calculando métricas avanzadas...")
        results = self._calculate_advanced_results(all_dates)
        
        # Imprimir resultados
        self._print_results(results)
        
        return results
    
    def _extract_dates(
        self, 
        historical_data: Dict[str, pd.DataFrame],
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> List:
        """Extrae y filtra fechas únicas de los datos"""
        all_dates = set()
        
        for df in historical_data.values():
            if 'snapshotTime' in df.columns:
                all_dates.update(pd.to_datetime(df['snapshotTime']).dt.date)
            elif 'timestamp' in df.columns:
                all_dates.update(pd.to_datetime(df['timestamp']).dt.date)
        
        all_dates = sorted(list(all_dates))
        
        # Filtrar por fechas
        if start_date:
            start = pd.to_datetime(start_date).date()
            all_dates = [d for d in all_dates if d >= start]
        if end_date:
            end = pd.to_datetime(end_date).date()
            all_dates = [d for d in all_dates if d <= end]
        
        return all_dates
    
    def _get_signals_for_date(
        self, 
        historical_data: Dict[str, pd.DataFrame], 
        date
    ) -> List[Dict]:
        """Obtiene señales para una fecha (sin mirar al futuro)"""
        signals = []
        
        for epic, df in historical_data.items():
            # Determinar columna de fecha
            if 'snapshotTime' in df.columns:
                df['date'] = pd.to_datetime(df['snapshotTime']).dt.date
            elif 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp']).dt.date
            else:
                continue
            
            # Solo usar datos hasta la fecha actual (no futuro)
            historical_subset = df[df['date'] <= date].copy()
            
            if len(historical_subset) < Config.SMA_LONG:
                continue
            
            # Analizar
            analysis = self.strategy.analyze(historical_subset, epic)
            signals.append(analysis)
        
        return signals
    
    def _open_position(self, signal: Dict, date) -> Optional[Dict]:
        """Abre una posición simulada"""
        price = signal['current_price']
        direction = signal['signal']
        
        # Calcular tamaño de posición
        available_capital = self.capital * Config.TARGET_PERCENT_OF_AVAILABLE
        position_size = available_capital / max(1, Config.MAX_POSITIONS)
        
        if position_size > self.capital:
            return None
        
        # Calcular unidades
        units = position_size / price
        
        # Calcular SL y TP (usar valores estáticos de Config)
        if direction == 'BUY':
            stop_loss = price * (1 - Config.STOP_LOSS_PERCENT_BUY)
            take_profit = price * (1 + Config.TAKE_PROFIT_PERCENT_BUY)
        else:
            stop_loss = price * (1 + Config.STOP_LOSS_PERCENT_SELL)
            take_profit = price * (1 - Config.TAKE_PROFIT_PERCENT_SELL)
        
        # Restar capital
        self.capital -= position_size
        
        position = {
            'epic': signal['epic'],
            'direction': direction,
            'entry_price': price,
            'entry_date': date,
            'units': units,
            'position_size': position_size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'current_price': price,
            'confidence': signal['confidence']
        }
        
        return position
    
    def _update_positions(
        self, 
        positions: List[Dict], 
        historical_data: Dict, 
        date
    ) -> List[Dict]:
        """Actualiza posiciones y cierra las que tocan SL/TP"""
        updated_positions = []
        
        for position in positions:
            epic = position['epic']
            
            if epic not in historical_data:
                updated_positions.append(position)
                continue
            
            df = historical_data[epic]
            
            # Obtener precio del día
            if 'snapshotTime' in df.columns:
                df['date'] = pd.to_datetime(df['snapshotTime']).dt.date
            elif 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp']).dt.date
            
            day_data = df[df['date'] == date]
            
            if day_data.empty:
                updated_positions.append(position)
                continue
            
            current_price = safe_float(day_data.iloc[-1]['closePrice'])
            position['current_price'] = current_price
            
            # Verificar SL/TP
            closed = False
            
            if position['direction'] == 'BUY':
                if current_price <= position['stop_loss']:
                    self._close_position(position, position['stop_loss'], date, 'STOP_LOSS')
                    closed = True
                elif current_price >= position['take_profit']:
                    self._close_position(position, position['take_profit'], date, 'TAKE_PROFIT')
                    closed = True
            else:  # SELL
                if current_price >= position['stop_loss']:
                    self._close_position(position, position['stop_loss'], date, 'STOP_LOSS')
                    closed = True
                elif current_price <= position['take_profit']:
                    self._close_position(position, position['take_profit'], date, 'TAKE_PROFIT')
                    closed = True
            
            if not closed:
                updated_positions.append(position)
        
        return updated_positions
    
    def _close_position(self, position: Dict, exit_price: float, exit_date, reason: str):
        """Cierra posición y registra trade"""
        entry_price = position['entry_price']
        units = position['units']
        direction = position['direction']
        entry_date = position['entry_date']
        
        # Calcular P&L
        if direction == 'BUY':
            pnl = (exit_price - entry_price) * units
        else:
            pnl = (entry_price - exit_price) * units
        
        # Devolver capital
        self.capital += position['position_size'] + pnl
        
        # Calcular duración
        if isinstance(entry_date, datetime):
            duration_hours = (exit_date - entry_date).total_seconds() / 3600
        else:
            duration_hours = (exit_date - entry_date).days * 24
        
        # Obtener info temporal
        exit_dt = pd.to_datetime(exit_date)
        day_of_week = exit_dt.strftime('%A')
        hour_of_day = exit_dt.hour if hasattr(exit_dt, 'hour') else 12
        
        # Crear trade
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
            pnl_percent=(pnl / position['position_size']) * 100,
            exit_reason=reason,
            confidence=position['confidence'],
            duration_hours=duration_hours,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day
        )
        
        self.trades.append(trade)
    
    def _calculate_equity(
        self, 
        open_positions: List[Dict], 
        historical_data: Dict, 
        date
    ) -> float:
        """Calcula equity total"""
        total = self.capital
        
        for position in open_positions:
            if position['direction'] == 'BUY':
                pnl = (position['current_price'] - position['entry_price']) * position['units']
            else:
                pnl = (position['entry_price'] - position['current_price']) * position['units']
            
            total += position['position_size'] + pnl
        
        return total
    
    def _calculate_advanced_results(self, all_dates: List) -> BacktestResults:
        """Calcula todas las métricas avanzadas"""
        
        # Crear DataFrame de equity curve
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        equity_df = equity_df.set_index('date')
        
        # Calcular returns diarios
        equity_df['returns'] = equity_df['equity'].pct_change()
        daily_returns = equity_df['returns'].dropna().tolist()
        
        # Basic stats
        total_return = self.capital - self.initial_capital
        total_return_percent = (total_return / self.initial_capital) * 100
        
        # CAGR
        years = len(all_dates) / 365.25
        cagr = ((self.capital / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
        
        # Drawdown analysis
        dd_stats = self._calculate_drawdown_stats(equity_df)
        
        # Risk metrics
        risk_metrics = self._calculate_risk_metrics(daily_returns, cagr, dd_stats['max_drawdown'])
        
        # Trade stats
        trade_stats = self._calculate_trade_stats()
        
        # Temporal analysis
        temporal_stats = self._calculate_temporal_analysis()
        
        # Crear resultado
        results = BacktestResults(
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
            **temporal_stats
        )
        
        return results
    
    def _calculate_drawdown_stats(self, equity_df: pd.DataFrame) -> Dict:
        """Calcula estadísticas de drawdown"""
        equity_series = equity_df['equity']
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        
        max_dd = drawdown.min()
        avg_dd = drawdown[drawdown < 0].mean() if len(drawdown[drawdown < 0]) > 0 else 0
        
        # Duración del máximo drawdown
        dd_duration = 0
        recovery_time = 0
        in_dd = False
        dd_start = None
        recovery_start = None
        
        for date, dd_value in drawdown.items():
            if dd_value < -1 and not in_dd:  # Entrando en drawdown
                in_dd = True
                dd_start = date
            elif dd_value >= 0 and in_dd:  # Recuperado
                if dd_start:
                    duration = (date - dd_start).days
                    dd_duration = max(dd_duration, duration)
                in_dd = False
                dd_start = None
        
        return {
            'max_drawdown': abs(max_dd),
            'avg_drawdown': abs(avg_dd),
            'max_drawdown_duration_days': dd_duration,
            'recovery_time_days': dd_duration  # Simplificado
        }
    
    def _calculate_risk_metrics(
        self, 
        daily_returns: List[float], 
        cagr: float,
        max_dd: float
    ) -> Dict:
        """Calcula métricas de riesgo ajustado"""
        if not daily_returns or len(daily_returns) < 2:
            return {
                'sharpe_ratio': 0,
                'sortino_ratio': 0,
                'calmar_ratio': 0,
                'mar_ratio': 0,
                'volatility': 0
            }
        
        returns_array = np.array(daily_returns)
        
        # Volatility (annualized)
        volatility = np.std(returns_array) * np.sqrt(252) * 100
        
        # Sharpe Ratio (asumiendo rf=0 para simplificar)
        mean_return = np.mean(returns_array)
        sharpe = (mean_return / np.std(returns_array)) * np.sqrt(252) if np.std(returns_array) > 0 else 0
        
        # Sortino Ratio (solo downside volatility)
        downside_returns = returns_array[returns_array < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else np.std(returns_array)
        sortino = (mean_return / downside_std) * np.sqrt(252) if downside_std > 0 else 0
        
        # Calmar Ratio
        calmar = cagr / max_dd if max_dd > 0 else 0
        
        # MAR Ratio (similar a Calmar)
        mar = calmar
        
        return {
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'mar_ratio': mar,
            'volatility': volatility
        }
    
    def _calculate_trade_stats(self) -> Dict:
        """Calcula estadísticas de trades"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'largest_win': 0,
                'largest_loss': 0,
                'profit_factor': 0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0
            }
        
        winners = [t for t in self.trades if t.is_winner]
        losers = [t for t in self.trades if not t.is_winner]
        
        total_wins = sum(t.pnl for t in winners)
        total_losses = abs(sum(t.pnl for t in losers))
        
        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in self.trades:
            if trade.is_winner:
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
        
        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'win_rate': (len(winners) / len(self.trades)) * 100,
            'avg_win': np.mean([t.pnl for t in winners]) if winners else 0,
            'avg_loss': np.mean([t.pnl for t in losers]) if losers else 0,
            'largest_win': max([t.pnl for t in winners]) if winners else 0,
            'largest_loss': min([t.pnl for t in losers]) if losers else 0,
            'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
            'max_consecutive_wins': max_consec_wins,
            'max_consecutive_losses': max_consec_losses
        }
    
    def _calculate_temporal_analysis(self) -> Dict:
        """Analiza performance por tiempo"""
        if not self.trades:
            return {
                'performance_by_day': {},
                'performance_by_hour': {},
                'performance_by_month': {}
            }
        
        # Por día de la semana
        by_day = {}
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            day_trades = [t for t in self.trades if t.day_of_week == day]
            if day_trades:
                winners = [t for t in day_trades if t.is_winner]
                by_day[day] = {
                    'total_trades': len(day_trades),
                    'win_rate': (len(winners) / len(day_trades)) * 100,
                    'total_pnl': sum(t.pnl for t in day_trades),
                    'avg_pnl': np.mean([t.pnl for t in day_trades])
                }
        
        # Por hora (simplificado: mañana/tarde)
        by_hour = {
            'morning': [],  # 9-13
            'afternoon': [],  # 13-18
            'evening': []  # 18-22
        }
        
        for trade in self.trades:
            if 9 <= trade.hour_of_day < 13:
                by_hour['morning'].append(trade)
            elif 13 <= trade.hour_of_day < 18:
                by_hour['afternoon'].append(trade)
            else:
                by_hour['evening'].append(trade)
        
        by_hour_stats = {}
        for period, trades in by_hour.items():
            if trades:
                winners = [t for t in trades if t.is_winner]
                by_hour_stats[period] = {
                    'total_trades': len(trades),
                    'win_rate': (len(winners) / len(trades)) * 100,
                    'total_pnl': sum(t.pnl for t in trades),
                    'avg_pnl': np.mean([t.pnl for t in trades])
                }
        
        return {
            'performance_by_day': by_day,
            'performance_by_hour': by_hour_stats,
            'performance_by_month': {}  # TODO: implementar si necesario
        }
    
    def _create_empty_results(self) -> BacktestResults:
        """Crea resultado vacío en caso de error"""
        return BacktestResults(
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
            total_return=0,
            total_return_percent=0,
            cagr=0
        )
    
    def _print_results(self, results: BacktestResults):
        """Imprime resultados formateados"""
        logger.info("\n" + "="*80)
        logger.info("📊 RESULTADOS DEL BACKTESTING EXHAUSTIVO")
        logger.info("="*80)
        
        # CAPITAL
        logger.info("\n💰 RENDIMIENTO DE CAPITAL")
        logger.info("-"*80)
        logger.info(f"Capital inicial:        €{results.initial_capital:,.2f}")
        logger.info(f"Capital final:          €{results.final_capital:,.2f}")
        logger.info(f"Retorno total:          €{results.total_return:,.2f} ({results.total_return_percent:.2f}%)")
        logger.info(f"CAGR (anualizado):      {results.cagr:.2f}%")
        
        # TRADES
        logger.info("\n📈 ESTADÍSTICAS DE TRADING")
        logger.info("-"*80)
        logger.info(f"Total operaciones:      {results.total_trades}")
        logger.info(f"Ganadoras:              {results.winning_trades} ({results.win_rate:.1f}%)")
        logger.info(f"Perdedoras:             {results.losing_trades}")
        logger.info(f"Ganancia promedio:      €{results.avg_win:.2f}")
        logger.info(f"Pérdida promedio:       €{results.avg_loss:.2f}")
        logger.info(f"Mayor ganancia:         €{results.largest_win:.2f}")
        logger.info(f"Mayor pérdida:          €{results.largest_loss:.2f}")
        logger.info(f"Profit factor:          {results.profit_factor:.2f}")
        
        # RACHA
        logger.info("\n🔥 RACHAS")
        logger.info("-"*80)
        logger.info(f"Máx. victorias consecutivas:  {results.max_consecutive_wins}")
        logger.info(f"Máx. pérdidas consecutivas:   {results.max_consecutive_losses}")
        
        # DRAWDOWN
        logger.info("\n📉 ANÁLISIS DE DRAWDOWN")
        logger.info("-"*80)
        logger.info(f"Máximo drawdown:        {results.max_drawdown:.2f}%")
        logger.info(f"Drawdown promedio:      {results.avg_drawdown:.2f}%")
        logger.info(f"Duración máx. DD:       {results.max_drawdown_duration_days} días")
        logger.info(f"Tiempo de recuperación: {results.recovery_time_days} días")
        
        # RISK METRICS
        logger.info("\n⚖️  MÉTRICAS DE RIESGO AJUSTADO")
        logger.info("-"*80)
        logger.info(f"Sharpe Ratio:           {results.sharpe_ratio:.3f}")
        logger.info(f"Sortino Ratio:          {results.sortino_ratio:.3f}")
        logger.info(f"Calmar Ratio:           {results.calmar_ratio:.3f}")
        logger.info(f"MAR Ratio:              {results.mar_ratio:.3f}")
        logger.info(f"Volatilidad (anual):    {results.volatility:.2f}%")
        
        # TEMPORAL ANALYSIS
        if results.performance_by_day:
            logger.info("\n📅 RENDIMIENTO POR DÍA DE LA SEMANA")
            logger.info("-"*80)
            for day, stats in results.performance_by_day.items():
                logger.info(
                    f"{day:12} | Trades: {stats['total_trades']:3} | "
                    f"Win Rate: {stats['win_rate']:5.1f}% | "
                    f"P&L: €{stats['total_pnl']:+8.2f}"
                )
        
        if results.performance_by_hour:
            logger.info("\n🕐 RENDIMIENTO POR PERÍODO DEL DÍA")
            logger.info("-"*80)
            for period, stats in results.performance_by_hour.items():
                logger.info(
                    f"{period.capitalize():12} | Trades: {stats['total_trades']:3} | "
                    f"Win Rate: {stats['win_rate']:5.1f}% | "
                    f"P&L: €{stats['total_pnl']:+8.2f}"
                )
        
        # INTERPRETACIÓN
        logger.info("\n💡 INTERPRETACIÓN DE RESULTADOS")
        logger.info("-"*80)
        self._print_interpretation(results)
        
        logger.info("\n" + "="*80)
    
    def _print_interpretation(self, results: BacktestResults):
        """Imprime interpretación de los resultados"""
        
        # Win Rate
        if results.win_rate >= 60:
            logger.info("✅ Win rate excelente (≥60%)")
        elif results.win_rate >= 50:
            logger.info("✅ Win rate bueno (≥50%)")
        elif results.win_rate >= 40:
            logger.info("⚠️  Win rate aceptable pero mejorable (40-50%)")
        else:
            logger.info("❌ Win rate bajo (<40%) - Estrategia necesita revisión")
        
        # Profit Factor
        if results.profit_factor >= 2.0:
            logger.info("✅ Profit factor excelente (≥2.0)")
        elif results.profit_factor >= 1.5:
            logger.info("✅ Profit factor bueno (≥1.5)")
        elif results.profit_factor >= 1.2:
            logger.info("⚠️  Profit factor aceptable (1.2-1.5)")
        else:
            logger.info("❌ Profit factor insuficiente (<1.2)")
        
        # Sharpe Ratio
        if results.sharpe_ratio >= 1.5:
            logger.info("✅ Sharpe ratio excelente (≥1.5)")
        elif results.sharpe_ratio >= 1.0:
            logger.info("✅ Sharpe ratio bueno (≥1.0)")
        elif results.sharpe_ratio >= 0.5:
            logger.info("⚠️  Sharpe ratio aceptable (0.5-1.0)")
        else:
            logger.info("❌ Sharpe ratio bajo (<0.5) - Mucho riesgo para el retorno")
        
        # Max Drawdown
        if results.max_drawdown <= 10:
            logger.info("✅ Drawdown bajo (≤10%) - Estrategia conservadora")
        elif results.max_drawdown <= 20:
            logger.info("✅ Drawdown moderado (10-20%)")
        elif results.max_drawdown <= 30:
            logger.info("⚠️  Drawdown alto (20-30%) - Requiere gestión de riesgo estricta")
        else:
            logger.info("❌ Drawdown muy alto (>30%) - Inaceptable para trading real")
        
        # CAGR
        if results.cagr >= 20:
            logger.info("✅ CAGR excelente (≥20% anual)")
        elif results.cagr >= 10:
            logger.info("✅ CAGR bueno (≥10% anual)")
        elif results.cagr >= 5:
            logger.info("⚠️  CAGR moderado (5-10% anual)")
        else:
            logger.info("❌ CAGR bajo (<5% anual) - No compensa el riesgo")
        
        # Calmar Ratio
        if results.calmar_ratio >= 1.0:
            logger.info("✅ Calmar ratio excelente (≥1.0) - Buen retorno vs drawdown")
        elif results.calmar_ratio >= 0.5:
            logger.info("✅ Calmar ratio aceptable (≥0.5)")
        else:
            logger.info("⚠️  Calmar ratio bajo - Drawdown elevado para el retorno obtenido")
        
        # Recovery time
        if results.recovery_time_days <= 30:
            logger.info("✅ Recuperación rápida de drawdowns (≤30 días)")
        elif results.recovery_time_days <= 90:
            logger.info("⚠️  Recuperación moderada de drawdowns (30-90 días)")
        else:
            logger.info("❌ Recuperación lenta de drawdowns (>90 días)")
        
        # Total trades
        if results.total_trades < 30:
            logger.info("⚠️  ADVERTENCIA: Pocos trades (<30) - Resultados poco significativos estadísticamente")
        elif results.total_trades < 100:
            logger.info("ℹ️  Número moderado de trades (30-100) - Añadir más datos mejoraría confianza")
        else:
            logger.info("✅ Buen número de trades (≥100) - Resultados estadísticamente significativos")
        
        # Recomendación final
        logger.info("\n🎯 RECOMENDACIÓN GENERAL:")
        
        # Scoring simple
        score = 0
        if results.win_rate >= 50: score += 1
        if results.profit_factor >= 1.5: score += 1
        if results.sharpe_ratio >= 1.0: score += 1
        if results.max_drawdown <= 20: score += 1
        if results.cagr >= 10: score += 1
        if results.total_trades >= 30: score += 1
        
        if score >= 5:
            logger.info("🟢 ESTRATEGIA PROMETEDORA - Considerar para trading real con capital reducido")
        elif score >= 3:
            logger.info("🟡 ESTRATEGIA NECESITA MEJORAS - Optimizar parámetros y probar más")
        else:
            logger.info("🔴 ESTRATEGIA NO RECOMENDABLE - Requiere cambios fundamentales")


def export_results_to_csv(results: BacktestResults, filename: str = 'backtest_results.csv'):
    """Exporta resultados a CSV"""
    if not results.trades:
        logger.warning("No hay trades para exportar")
        return
    
    # Convertir trades a DataFrame
    trades_data = []
    for trade in results.trades:
        trades_data.append({
            'epic': trade.epic,
            'direction': trade.direction,
            'entry_date': trade.entry_date,
            'exit_date': trade.exit_date,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'position_size': trade.position_size,
            'pnl': trade.pnl,
            'pnl_percent': trade.pnl_percent,
            'exit_reason': trade.exit_reason,
            'confidence': trade.confidence,
            'duration_hours': trade.duration_hours,
            'day_of_week': trade.day_of_week
        })
    
    df = pd.DataFrame(trades_data)
    df.to_csv(filename, index=False)
    logger.info(f"✅ Trades exportados a {filename}")


def export_summary_to_json(results: BacktestResults, filename: str = 'backtest_summary.json'):
    """Exporta resumen a JSON"""
    import json
    
    summary = {
        'capital': {
            'initial': results.initial_capital,
            'final': results.final_capital,
            'total_return': results.total_return,
            'total_return_percent': results.total_return_percent,
            'cagr': results.cagr
        },
        'trades': {
            'total': results.total_trades,
            'winning': results.winning_trades,
            'losing': results.losing_trades,
            'win_rate': results.win_rate,
            'profit_factor': results.profit_factor
        },
        'risk': {
            'max_drawdown': results.max_drawdown,
            'sharpe_ratio': results.sharpe_ratio,
            'sortino_ratio': results.sortino_ratio,
            'calmar_ratio': results.calmar_ratio,
            'volatility': results.volatility
        },
        'temporal': {
            'by_day': results.performance_by_day,
            'by_hour': results.performance_by_hour
        }
    }
    
    with open(filename, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    logger.info(f"✅ Resumen exportado a {filename}")