"""
Motor de backtesting para probar estrategias con datos históricos
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from strategies.intraday_strategy import IntradayStrategy
from trading.position_manager import PositionManager
from config import Config
from utils.helpers import safe_float

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Motor de backtesting para estrategias de trading"""
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.strategy = IntradayStrategy()
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        
    def run(self, historical_data: Dict[str, pd.DataFrame], start_date: str = None, end_date: str = None) -> Dict:
        """
        Ejecuta un backtest completo
        
        Args:
            historical_data: {epic: DataFrame con columnas [timestamp, closePrice, ...]}
            start_date: Fecha de inicio (formato: 'YYYY-MM-DD')
            end_date: Fecha de fin (formato: 'YYYY-MM-DD')
            
        Returns:
            Dict con resultados del backtest
        """
        logger.info("="*60)
        logger.info("🔬 INICIANDO BACKTESTING")
        logger.info("="*60)
        logger.info(f"Capital inicial: €{self.initial_capital:,.2f}")
        
        # Resetear estado
        self.capital = self.initial_capital
        self.trades = []
        self.equity_curve = []
        open_positions: List[Dict] = []
        
        # Preparar datos
        if not historical_data:
            logger.error("No hay datos históricos para backtest")
            return {}
        
        # Obtener todas las fechas únicas y ordenarlas
        all_dates = set()
        for df in historical_data.values():
            if 'snapshotTime' in df.columns:
                all_dates.update(pd.to_datetime(df['snapshotTime']).dt.date)
            elif 'timestamp' in df.columns:
                all_dates.update(pd.to_datetime(df['timestamp']).dt.date)
        
        all_dates = sorted(list(all_dates))
        
        # Filtrar por fechas si se especifican
        if start_date:
            start = pd.to_datetime(start_date).date()
            all_dates = [d for d in all_dates if d >= start]
        if end_date:
            end = pd.to_datetime(end_date).date()
            all_dates = [d for d in all_dates if d <= end]
        
        logger.info(f"Período: {all_dates[0]} a {all_dates[-1]} ({len(all_dates)} días)")
        
        # Simular día por día
        for current_date in all_dates:
            # Actualizar posiciones abiertas (simular cierre por SL/TP)
            open_positions = self._update_positions(open_positions, historical_data, current_date)
            
            # Buscar señales de trading
            signals = self._get_signals_for_date(historical_data, current_date)
            
            # Ejecutar operaciones basadas en señales
            for signal in signals:
                if len(open_positions) >= Config.MAX_POSITIONS:
                    break
                
                if signal['signal'] in ['BUY', 'SELL'] and signal['confidence'] >= Config.MIN_CONFIDENCE:
                    # Calcular tamaño de posición
                    available_capital = self.capital * Config.TARGET_PERCENT_OF_AVAILABLE
                    position_size = available_capital / max(len(signals), 1)
                    
                    # Simular entrada
                    position = self._open_position(signal, position_size, current_date)
                    if position:
                        open_positions.append(position)
            
            # Registrar equity del día
            total_equity = self._calculate_equity(open_positions, historical_data, current_date)
            self.equity_curve.append({
                'date': current_date,
                'equity': total_equity,
                'cash': self.capital,
                'open_positions': len(open_positions)
            })
        
        # Cerrar todas las posiciones al final
        for position in open_positions:
            self._close_position(position, position['current_price'], all_dates[-1], 'END_OF_BACKTEST')
        
        # Calcular estadísticas
        results = self._calculate_statistics()
        self._print_results(results)
        
        return results
    
    def _get_signals_for_date(self, historical_data: Dict[str, pd.DataFrame], date) -> List[Dict]:
        """Obtiene señales de trading para una fecha específica"""
        signals = []
        
        for epic, df in historical_data.items():
            # Filtrar datos hasta la fecha actual (simular que no conocemos el futuro)
            if 'snapshotTime' in df.columns:
                df['date'] = pd.to_datetime(df['snapshotTime']).dt.date
            elif 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp']).dt.date
            else:
                continue
            
            historical_subset = df[df['date'] <= date].copy()
            
            if len(historical_subset) < Config.SMA_LONG:
                continue
            
            # Analizar con la estrategia
            analysis = self.strategy.analyze(historical_subset, epic)
            signals.append(analysis)
        
        return signals
    
    def _open_position(self, signal: Dict, position_size: float, date) -> Dict:
        """Abre una posición simulada"""
        price = signal['current_price']
        direction = signal['signal']
        
        # Calcular cantidad de unidades
        units = position_size / price
        
        # Calcular SL y TP
        if direction == 'BUY':
            stop_loss = price * (1 - Config.STOP_LOSS_PERCENT_BUY)
            take_profit = price * (1 + Config.TAKE_PROFIT_PERCENT_BUY)
        else:
            stop_loss = price * (1 + Config.STOP_LOSS_PERCENT_SELL)
            take_profit = price * (1 - Config.TAKE_PROFIT_PERCENT_SELL)
        
        # Restar capital usado
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
        
        logger.info(f"📈 ABIERTA: {direction} {signal['epic']} @ €{price:.2f} | Size: €{position_size:.2f}")
        
        return position
    
    def _update_positions(self, positions: List[Dict], historical_data: Dict, date) -> List[Dict]:
        """Actualiza posiciones y cierra las que alcancen SL/TP"""
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
            
            # Usar precio de cierre del día
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
        """Cierra una posición y registra el trade"""
        entry_price = position['entry_price']
        units = position['units']
        direction = position['direction']
        
        # Calcular P&L
        if direction == 'BUY':
            pnl = (exit_price - entry_price) * units
        else:  # SELL
            pnl = (entry_price - exit_price) * units
        
        # Devolver capital + P&L
        self.capital += position['position_size'] + pnl
        
        # Registrar trade
        trade = {
            'epic': position['epic'],
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'entry_date': position['entry_date'],
            'exit_date': exit_date,
            'units': units,
            'pnl': pnl,
            'pnl_percent': (pnl / position['position_size']) * 100,
            'reason': reason,
            'confidence': position['confidence']
        }
        
        self.trades.append(trade)
        
        emoji = "✅" if pnl > 0 else "❌"
        logger.info(
            f"{emoji} CERRADA: {direction} {position['epic']} @ €{exit_price:.2f} | "
            f"P&L: €{pnl:.2f} ({trade['pnl_percent']:.1f}%) | {reason}"
        )
    
    def _calculate_equity(self, open_positions: List[Dict], historical_data: Dict, date) -> float:
        """Calcula el equity total (capital + valor de posiciones abiertas)"""
        total = self.capital
        
        for position in open_positions:
            # Valor actual de la posición
            current_value = position['current_price'] * position['units']
            
            if position['direction'] == 'BUY':
                pnl = (position['current_price'] - position['entry_price']) * position['units']
            else:
                pnl = (position['entry_price'] - position['current_price']) * position['units']
            
            total += position['position_size'] + pnl
        
        return total
    
    def _calculate_statistics(self) -> Dict:
        """Calcula estadísticas del backtest"""
        if not self.trades:
            return {
                'total_trades': 0,
                'final_capital': self.capital,
                'total_return': 0,
                'total_return_percent': 0
            }
        
        df_trades = pd.DataFrame(self.trades)
        
        winning_trades = df_trades[df_trades['pnl'] > 0]
        losing_trades = df_trades[df_trades['pnl'] < 0]
        
        total_return = self.capital - self.initial_capital
        total_return_percent = (total_return / self.initial_capital) * 100
        
        # Calcular drawdown
        equity_series = pd.Series([e['equity'] for e in self.equity_curve])
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        stats = {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / len(self.trades)) * 100 if self.trades else 0,
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_return': total_return,
            'total_return_percent': total_return_percent,
            'avg_win': winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0,
            'avg_loss': losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0,
            'largest_win': winning_trades['pnl'].max() if len(winning_trades) > 0 else 0,
            'largest_loss': losing_trades['pnl'].min() if len(losing_trades) > 0 else 0,
            'max_drawdown': max_drawdown,
            'profit_factor': abs(winning_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 and losing_trades['pnl'].sum() != 0 else float('inf'),
            'trades_detail': self.trades,
            'equity_curve': self.equity_curve
        }
        
        return stats
    
    def _print_results(self, results: Dict):
        """Imprime resultados del backtest"""
        logger.info("="*60)
        logger.info("📊 RESULTADOS DEL BACKTEST")
        logger.info("="*60)
        logger.info(f"Capital inicial:     €{results['initial_capital']:,.2f}")
        logger.info(f"Capital final:       €{results['final_capital']:,.2f}")
        logger.info(f"Retorno total:       €{results['total_return']:,.2f} ({results['total_return_percent']:.2f}%)")
        logger.info("-"*60)
        logger.info(f"Total operaciones:   {results['total_trades']}")
        logger.info(f"Ganadoras:           {results['winning_trades']} ({results['win_rate']:.1f}%)")
        logger.info(f"Perdedoras:          {results['losing_trades']}")
        logger.info("-"*60)
        logger.info(f"Ganancia promedio:   €{results['avg_win']:.2f}")
        logger.info(f"Pérdida promedio:    €{results['avg_loss']:.2f}")
        logger.info(f"Mayor ganancia:      €{results['largest_win']:.2f}")
        logger.info(f"Mayor pérdida:       €{results['largest_loss']:.2f}")
        logger.info(f"Profit factor:       {results['profit_factor']:.2f}")
        logger.info(f"Max drawdown:        {results['max_drawdown']:.2f}%")
        logger.info("="*60)


def export_results_to_csv(results: Dict, filename: str = 'backtest_results.csv'):
    """Exporta resultados a CSV"""
    if 'trades_detail' in results and results['trades_detail']:
        df = pd.DataFrame(results['trades_detail'])
        df.to_csv(filename, index=False)
        logger.info(f"✅ Resultados exportados a {filename}")