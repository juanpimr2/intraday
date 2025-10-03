"""
Sistema de seguimiento y evaluación de performance
Registra cada trade y calcula métricas clave
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Rastrea y evalúa el rendimiento del bot"""
    
    def __init__(self, trades_file='trades_history.csv', stats_file='performance_stats.json'):
        self.trades_file = trades_file
        self.stats_file = stats_file
        self._ensure_files()
    
    def _ensure_files(self):
        """Crea archivos si no existen"""
        if not Path(self.trades_file).exists():
            df = pd.DataFrame(columns=[
                'timestamp', 'epic', 'direction', 'entry_price', 'exit_price',
                'size', 'pnl', 'pnl_percent', 'reason', 'confidence', 'duration'
            ])
            df.to_csv(self.trades_file, index=False)
        
        if not Path(self.stats_file).exists():
            with open(self.stats_file, 'w') as f:
                json.dump({}, f)
    
    def log_trade(self, trade_data: dict):
        """
        Registra un trade cerrado
        
        Args:
            trade_data: {
                'epic': str,
                'direction': 'BUY'|'SELL',
                'entry_price': float,
                'exit_price': float,
                'entry_time': datetime,
                'exit_time': datetime,
                'size': float,
                'pnl': float,
                'reason': 'STOP_LOSS'|'TAKE_PROFIT'|'MANUAL',
                'confidence': float
            }
        """
        try:
            df = pd.read_csv(self.trades_file)
            
            duration = (trade_data['exit_time'] - trade_data['entry_time']).total_seconds() / 3600  # horas
            
            new_row = {
                'timestamp': trade_data['exit_time'].isoformat(),
                'epic': trade_data['epic'],
                'direction': trade_data['direction'],
                'entry_price': trade_data['entry_price'],
                'exit_price': trade_data['exit_price'],
                'size': trade_data['size'],
                'pnl': trade_data['pnl'],
                'pnl_percent': (trade_data['pnl'] / (trade_data['entry_price'] * trade_data['size'])) * 100,
                'reason': trade_data['reason'],
                'confidence': trade_data.get('confidence', 0),
                'duration': duration
            }
            
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(self.trades_file, index=False)
            
            logger.info(f"✅ Trade registrado: {trade_data['epic']} {trade_data['direction']} - P&L: €{trade_data['pnl']:.2f}")
            
        except Exception as e:
            logger.error(f"Error registrando trade: {e}")
    
    def calculate_metrics(self, period_days: int = 30) -> dict:
        """
        Calcula métricas de performance
        
        Args:
            period_days: Período de análisis en días
            
        Returns:
            dict con métricas
        """
        try:
            df = pd.read_csv(self.trades_file)
            
            if df.empty:
                return {'error': 'No hay trades registrados'}
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filtrar por período
            cutoff_date = datetime.now() - pd.Timedelta(days=period_days)
            df = df[df['timestamp'] >= cutoff_date]
            
            if df.empty:
                return {'error': f'No hay trades en los últimos {period_days} días'}
            
            # Separar wins y losses
            wins = df[df['pnl'] > 0]
            losses = df[df['pnl'] < 0]
            
            # Métricas básicas
            total_trades = len(df)
            win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
            
            total_pnl = df['pnl'].sum()
            avg_pnl = df['pnl'].mean()
            
            avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
            avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
            
            # Profit Factor
            gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
            gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Sharpe Ratio (simplificado)
            if len(df) > 1:
                returns = df['pnl_percent']
                sharpe_ratio = returns.mean() / returns.std() if returns.std() > 0 else 0
                sharpe_ratio = sharpe_ratio * np.sqrt(252)  # Anualizado
            else:
                sharpe_ratio = 0
            
            # Maximum Drawdown
            cumulative_pnl = df['pnl'].cumsum()
            running_max = cumulative_pnl.expanding().max()
            drawdown = cumulative_pnl - running_max
            max_drawdown = drawdown.min()
            max_drawdown_pct = (max_drawdown / running_max.max()) * 100 if running_max.max() > 0 else 0
            
            # Expectancy
            expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * abs(avg_loss))
            
            # Por activo
            by_asset = df.groupby('epic').agg({
                'pnl': ['count', 'sum', 'mean'],
                'pnl_percent': 'mean'
            }).round(2)
            
            # Por razón de cierre
            by_reason = df.groupby('reason').agg({
                'pnl': ['count', 'sum', 'mean']
            }).round(2)
            
            metrics = {
                'period_days': period_days,
                'total_trades': int(total_trades),
                'winning_trades': int(len(wins)),
                'losing_trades': int(len(losses)),
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'avg_pnl_per_trade': round(avg_pnl, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'profit_factor': round(profit_factor, 2),
                'sharpe_ratio': round(sharpe_ratio, 2),
                'max_drawdown': round(max_drawdown, 2),
                'max_drawdown_pct': round(max_drawdown_pct, 2),
                'expectancy': round(expectancy, 2),
                'avg_duration_hours': round(df['duration'].mean(), 2),
                'by_asset': by_asset.to_dict(),
                'by_reason': by_reason.to_dict()
            }
            
            # Guardar stats
            with open(self.stats_file, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculando métricas: {e}")
            return {'error': str(e)}
    
    def print_report(self, period_days: int = 30):
        """Imprime reporte de performance"""
        metrics = self.calculate_metrics(period_days)
        
        if 'error' in metrics:
            print(f"⚠️  {metrics['error']}")
            return
        
        print("="*70)
        print(f"📊 REPORTE DE PERFORMANCE - Últimos {period_days} días")
        print("="*70)
        print(f"\n📈 RESUMEN GENERAL")
        print(f"   Total operaciones:     {metrics['total_trades']}")
        print(f"   Ganadoras:             {metrics['winning_trades']} ({metrics['win_rate']:.1f}%)")
        print(f"   Perdedoras:            {metrics['losing_trades']}")
        print(f"   Win Rate:              {metrics['win_rate']:.2f}%")
        
        print(f"\n💰 PERFORMANCE FINANCIERA")
        print(f"   P&L Total:             €{metrics['total_pnl']:,.2f}")
        print(f"   P&L Promedio:          €{metrics['avg_pnl_per_trade']:.2f}")
        print(f"   Ganancia promedio:     €{metrics['avg_win']:.2f}")
        print(f"   Pérdida promedio:      €{metrics['avg_loss']:.2f}")
        print(f"   Profit Factor:         {metrics['profit_factor']:.2f}")
        
        print(f"\n📊 MÉTRICAS DE RIESGO")
        print(f"   Sharpe Ratio:          {metrics['sharpe_ratio']:.2f}")
        print(f"   Max Drawdown:          €{metrics['max_drawdown']:.2f} ({metrics['max_drawdown_pct']:.2f}%)")
        print(f"   Expectancy:            €{metrics['expectancy']:.2f}")
        print(f"   Duración promedio:     {metrics['avg_duration_hours']:.2f} horas")
        
        print("\n" + "="*70)
        
        # Evaluación
        self._print_evaluation(metrics)
    
    def _print_evaluation(self, metrics: dict):
        """Imprime evaluación cualitativa"""
        print("\n🎯 EVALUACIÓN")
        
        score = 0
        comments = []
        
        # Win Rate
        if metrics['win_rate'] >= 55:
            score += 2
            comments.append("✅ Win rate excelente (>55%)")
        elif metrics['win_rate'] >= 50:
            score += 1
            comments.append("✅ Win rate bueno (>50%)")
        else:
            comments.append("⚠️  Win rate bajo (<50%) - Necesita optimización")
        
        # Profit Factor
        if metrics['profit_factor'] >= 2.0:
            score += 2
            comments.append("✅ Profit factor excelente (>2.0)")
        elif metrics['profit_factor'] >= 1.5:
            score += 1
            comments.append("✅ Profit factor aceptable (>1.5)")
        else:
            comments.append("⚠️  Profit factor bajo (<1.5) - Revisar RR ratio")
        
        # Sharpe Ratio
        if metrics['sharpe_ratio'] >= 1.0:
            score += 2
            comments.append("✅ Sharpe ratio bueno (>1.0)")
        elif metrics['sharpe_ratio'] >= 0.5:
            score += 1
            comments.append("✅ Sharpe ratio aceptable (>0.5)")
        else:
            comments.append("⚠️  Sharpe ratio bajo - Volatilidad alta vs retorno")
        
        # Max Drawdown
        if abs(metrics['max_drawdown_pct']) <= 15:
            score += 2
            comments.append("✅ Drawdown controlado (<15%)")
        elif abs(metrics['max_drawdown_pct']) <= 25:
            score += 1
            comments.append("⚠️  Drawdown moderado (15-25%)")
        else:
            comments.append("❌ Drawdown alto (>25%) - RIESGO ELEVADO")
        
        for comment in comments:
            print(f"   {comment}")
        
        print(f"\n   Puntuación: {score}/8")
        
        if score >= 6:
            print("   Veredicto: ✅ BOT PERFORMANDO BIEN")
        elif score >= 4:
            print("   Veredicto: ⚠️  BOT NECESITA MEJORAS")
        else:
            print("   Veredicto: ❌ BOT NECESITA REVISIÓN CRÍTICA")


# Uso:
# tracker = PerformanceTracker()
# tracker.print_report(period_days=30)