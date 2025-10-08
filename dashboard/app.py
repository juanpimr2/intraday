# dashboard/app.py
"""
Dashboard web para monitorear el bot de trading
VERSIÓN CORREGIDA: usa bot_state global (sin circular imports)
"""

from flask import Flask, render_template, jsonify, send_file, request
from flask_cors import CORS
import logging
from datetime import datetime, timedelta
import pandas as pd
import os
from io import BytesIO

from api.capital_client import CapitalClient
from config import Config
from utils.helpers import safe_float
from database.database_manager import DatabaseManager
from database.queries.analytics import AnalyticsQueries
from backtesting.backtest_engine import BacktestEngine

# ✅ IMPORTAR EL ESTADO GLOBAL (sin circular imports)
from utils.bot_state import bot_state

app = Flask(__name__)
CORS(app)
logger = logging.getLogger(__name__)

# Clientes globales
api_client = None
db_manager = None
analytics = None


def get_api_client():
    """Obtiene o crea el cliente API"""
    global api_client
    if api_client is None:
        api_client = CapitalClient()
        if not api_client.authenticate():
            logger.error("Error de autenticación")
            return None
    return api_client


def get_db_manager():
    """Obtiene el database manager"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager


def get_analytics():
    """Obtiene analytics queries"""
    global analytics
    if analytics is None:
        analytics = AnalyticsQueries()
    return analytics

# ============================================
# RUTAS PRINCIPALES
# ============================================

@app.route('/')
def index():
    """Página principal del dashboard"""
    return render_template('index.html')


# ============================================
# API ENDPOINTS BÁSICOS
# ============================================

@app.route('/api/account')
def get_account():
    """Endpoint para obtener información de la cuenta"""
    api = get_api_client()
    if not api:
        return jsonify({'error': 'No autenticado'}), 401
    
    account_info = api.get_account_info()
    
    if not account_info:
        return jsonify({'error': 'No se pudo obtener información de cuenta'}), 500
    
    balance = safe_float(account_info.get('balance', {}).get('balance', 0))
    available = safe_float(account_info.get('balance', {}).get('available', 0))
    margin_used = balance - available
    
    return jsonify({
        'balance': balance,
        'available': available,
        'margin_used': margin_used,
        'margin_percent': (margin_used / balance * 100) if balance > 0 else 0,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/positions')
def get_positions():
    """Endpoint para obtener posiciones abiertas"""
    api = get_api_client()
    if not api:
        return jsonify({'error': 'No autenticado'}), 401
    
    positions = api.get_positions()
    
    formatted_positions = []
    for pos in positions:
        position_data = pos.get('position', {})
        
        formatted_positions.append({
            'epic': pos.get('market', {}).get('epic', 'Unknown'),
            'instrument_name': pos.get('market', {}).get('instrumentName', 'Unknown'),
            'direction': position_data.get('direction', 'Unknown'),
            'size': safe_float(position_data.get('size', 0)),
            'level': safe_float(position_data.get('level', 0)),
            'currency': position_data.get('currency', 'EUR'),
            'createdDate': position_data.get('createdDate', ''),
            'stopLevel': safe_float(position_data.get('stopLevel', 0)),
            'limitLevel': safe_float(position_data.get('profitLevel', 0)),
            'dealId': position_data.get('dealId', '')
        })
    
    return jsonify({
        'positions': formatted_positions,
        'count': len(formatted_positions),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/config')
def get_config():
    """Endpoint para obtener configuración del bot"""
    return jsonify({
        'assets': Config.ASSETS,
        'max_positions': Config.MAX_POSITIONS,
        'target_percent': Config.TARGET_PERCENT_OF_AVAILABLE * 100,
        'max_risk': Config.MAX_CAPITAL_RISK * 100,
        'timeframe': Config.TIMEFRAME,
        'trading_hours': f"{Config.START_HOUR}:00 - {Config.END_HOUR}:00",
        'sl_tp_mode': Config.SL_TP_MODE,
        'enable_mtf': Config.ENABLE_MTF,
        'enable_adx_filter': Config.ENABLE_ADX_FILTER
    })

@app.route('/api/status')
def get_status():
    """Endpoint para verificar estado del bot"""
    try:
        now = datetime.now()
        is_trading_hours = (
            now.weekday() < 5 and
            Config.START_HOUR <= now.hour < Config.END_HOUR
        )
        
        # ✅ Usar el estado global (sin BotController)
        status = bot_state.get_status()
        
        return jsonify({
            'status': 'running' if status['running'] else 'paused',
            'running': status['running'],
            'is_trading_hours': is_trading_hours,
            'manual_override': status['manual_override'],
            'last_command': status['last_command'],
            'last_heartbeat': status['last_heartbeat'],
            'current_time': now.isoformat(),
            'next_scan': 'In progress' if (is_trading_hours and status['running']) else 'Paused' if not status['running'] else 'Waiting for trading hours'
        })
    except Exception as e:
        logger.error(f"Error obteniendo estado: {e}")
        return jsonify({
            'status': 'error',
            'running': False,
            'error': str(e)
        }), 500


@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Inicia el bot manualmente"""
    try:
        # ✅ Usar el estado global
        bot_state.start()
        
        logger.info("✅ Bot iniciado desde dashboard")
        
        return jsonify({
            'success': True,
            'message': 'Bot iniciado correctamente',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Error iniciando bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Pausa el bot manualmente"""
    try:
        # ✅ Usar el estado global
        bot_state.stop()
        
        logger.info("⏸️ Bot pausado desde dashboard")
        
        return jsonify({
            'success': True,
            'message': 'Bot pausado correctamente',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Error pausando bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINTS DE HISTORIAL DE TRADES
# ============================================

@app.route('/api/trades/history')
def get_trades_history():
    """Obtiene historial de trades desde la BD"""
    try:
        analytics = get_analytics()
        
        session_id = request.args.get('session_id', type=int)
        limit = request.args.get('limit', 100, type=int)
        
        if session_id:
            trades = analytics.get_trades_by_session(session_id)
        else:
            trades = analytics.get_recent_trades(limit=limit)
        
        return jsonify({
            'trades': trades,
            'count': len(trades),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trades/stats')
def get_trades_stats():
    """Obtiene estadísticas de trades"""
    try:
        analytics = get_analytics()
        
        session_id = request.args.get('session_id', type=int)
        
        if session_id:
            stats = analytics.get_trade_analysis(session_id=session_id)
        else:
            stats = analytics.get_global_stats()
        
        return jsonify({
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# ENDPOINTS DE EXPORT
# ============================================

@app.route('/api/trades/export/<format>')
def export_trades(format):
    """Exporta trades a CSV o Excel"""
    try:
        analytics = get_analytics()
        session_id = request.args.get('session_id', type=int)
        
        if format not in ['csv', 'excel']:
            return jsonify({'error': 'Formato no válido. Use csv o excel'}), 400
        
        if session_id:
            filepath = analytics.export_trades(
                session_id=session_id,
                format=format
            )
        else:
            filepath = analytics.export_all_trades(format=format)
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': 'No se pudo generar el archivo'}), 500
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=f'trades_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{format}'
        )
        
    except Exception as e:
        logger.error(f"Error exportando trades: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/report/full')
def export_full_report():
    """Genera reporte completo en Excel"""
    try:
        analytics = get_analytics()
        session_id = request.args.get('session_id', type=int)
        
        if not session_id:
            return jsonify({'error': 'Se requiere session_id'}), 400
        
        filepath = analytics.export_full_report(
            session_id=session_id,
            format='excel'
        )
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': 'No se pudo generar el reporte'}), 500
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=f'trading_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
    except Exception as e:
        logger.error(f"Error generando reporte: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# ENDPOINTS DE SESIONES
# ============================================

@app.route('/api/sessions/list')
def get_sessions():
    """Lista todas las sesiones de trading"""
    try:
        analytics = get_analytics()
        
        limit = request.args.get('limit', 20, type=int)
        sessions = analytics.get_sessions_summary(limit=limit)
        
        return jsonify({
            'sessions': sessions,
            'count': len(sessions),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo sesiones: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sessions/<int:session_id>')
def get_session_detail(session_id):
    """Obtiene detalle completo de una sesión"""
    try:
        analytics = get_analytics()
        
        session = analytics.get_session_info(session_id)
        trades = analytics.get_trades_by_session(session_id)
        stats = analytics.get_trade_analysis(session_id=session_id)
        signals = analytics.get_signals_by_session(session_id)
        
        return jsonify({
            'session': session,
            'trades': trades,
            'stats': stats,
            'signals': signals,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo detalle de sesión: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# ENDPOINTS DE BACKTESTING
# ============================================

@app.route('/api/backtest/run', methods=['POST'])
def run_backtest():
    """Ejecuta un backtest con datos históricos"""
    try:
        data = request.get_json()
        
        days = data.get('days', 30)
        initial_capital = data.get('initial_capital', 10000.0)
        assets = data.get('assets', Config.ASSETS)
        
        if days < 1 or days > 365:
            return jsonify({'error': 'days debe estar entre 1 y 365'}), 400
        
        if initial_capital < 100:
            return jsonify({'error': 'Capital mínimo: 100'}), 400
        
        api = get_api_client()
        if not api:
            return jsonify({'error': 'No autenticado'}), 401
        
        historical_data = {}
        for asset in assets:
            try:
                market_data = api.get_market_data(
                    asset,
                    Config.TIMEFRAME,
                    max_values=days * 24
                )
                
                if market_data and 'prices' in market_data:
                    df = pd.DataFrame(market_data['prices'])
                    
                    for col in ['closePrice', 'openPrice', 'highPrice', 'lowPrice']:
                        if col in df.columns:
                            df[col] = df[col].apply(safe_float)
                    
                    df = df.dropna(subset=['closePrice'])
                    
                    if not df.empty:
                        historical_data[asset] = df
                        
            except Exception as e:
                logger.warning(f"Error obteniendo datos de {asset}: {e}")
                continue
        
        if not historical_data:
            return jsonify({'error': 'No se pudieron obtener datos históricos'}), 500
        
        engine = BacktestEngine(initial_capital=initial_capital)
        results = engine.run(historical_data)
        
        return jsonify({
            'results': {
                'initial_capital': results.get('initial_capital', 0),
                'final_capital': results.get('final_capital', 0),
                'total_return': results.get('total_return', 0),
                'total_return_percent': results.get('total_return_percent', 0),
                'total_trades': results.get('total_trades', 0),
                'winning_trades': results.get('winning_trades', 0),
                'losing_trades': results.get('losing_trades', 0),
                'win_rate': results.get('win_rate', 0),
                'avg_win': results.get('avg_win', 0),
                'avg_loss': results.get('avg_loss', 0),
                'profit_factor': results.get('profit_factor', 0),
                'max_drawdown': results.get('max_drawdown', 0)
            },
            'equity_curve': results.get('equity_curve', []),
            'trades_detail': results.get('trades_detail', []),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en backtest: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# ENDPOINTS DE SEÑALES
# ============================================

@app.route('/api/signals/recent')
def get_recent_signals():
    """Obtiene las señales más recientes"""
    try:
        analytics = get_analytics()
        
        limit = request.args.get('limit', 50, type=int)
        signals = analytics.get_recent_signals(limit=limit)
        
        return jsonify({
            'signals': signals,
            'count': len(signals),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo señales: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# HEALTH CHECK
# ============================================

@app.route('/api/health')
def health_check():
    """Health check del dashboard"""
    try:
        db = get_db_manager()
        db_healthy = db is not None and db.db is not None
        
        api = get_api_client()
        api_healthy = api is not None
        
        return jsonify({
            'status': 'healthy' if (db_healthy and api_healthy) else 'degraded',
            'database': 'connected' if db_healthy else 'disconnected',
            'api': 'connected' if api_healthy else 'disconnected',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ============================================
# RUN
# ============================================

def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """Inicia el servidor del dashboard"""
    logger.info(f"🌐 Dashboard disponible en http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_dashboard(debug=True)