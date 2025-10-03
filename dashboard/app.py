"""
Dashboard web mejorado para monitorear y controlar el bot de trading
"""

from flask import Flask, render_template, jsonify, send_file, request
import logging
import os
import pandas as pd
from datetime import datetime
from api.capital_client import CapitalClient
from config import Config
from utils.helpers import safe_float
from utils.bot_controller import BotController

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Cliente API y controlador globales
api_client = None
bot_controller = BotController()


def get_api_client():
    """Obtiene o crea el cliente API"""
    global api_client
    if api_client is None:
        api_client = CapitalClient()
        if not api_client.authenticate():
            logger.error("Error de autenticación")
            return None
    return api_client


@app.route('/')
def index():
    """Página principal del dashboard"""
    return render_template('index.html')


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
        market_data = pos.get('market', {})
        
        # Epic
        epic = market_data.get('epic') or market_data.get('instrumentName') or position_data.get('epic') or 'Unknown'
        
        # Take Profit - Buscar en múltiples lugares
        limit_level = (
            safe_float(position_data.get('limitLevel', 0)) or
            safe_float(position_data.get('profitLevel', 0)) or
            safe_float(position_data.get('limitPrice', 0)) or
            safe_float(position_data.get('limit', 0)) or
            0
        )
        
        if limit_level == 0 and 'limit' in position_data and isinstance(position_data['limit'], dict):
            limit_level = safe_float(position_data['limit'].get('level', 0))
        
        formatted_positions.append({
            'epic': epic,
            'direction': position_data.get('direction', 'Unknown'),
            'size': safe_float(position_data.get('size', 0)),
            'level': safe_float(position_data.get('level', 0)),
            'currency': position_data.get('currency', 'EUR'),
            'createdDate': position_data.get('createdDate', ''),
            'stopLevel': safe_float(position_data.get('stopLevel', 0)),
            'limitLevel': limit_level,
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
        'trading_hours': f"{Config.START_HOUR}:00 - {Config.END_HOUR}:00"
    })


@app.route('/api/status')
def get_status():
    """Endpoint para verificar estado del bot"""
    now = datetime.now()
    is_trading_hours = (
        now.weekday() < 5 and
        Config.START_HOUR <= now.hour < Config.END_HOUR
    )
    
    # Obtener estado del controlador
    bot_state = bot_controller.get_status()
    
    return jsonify({
        'status': 'running' if bot_state['running'] else 'stopped',
        'running': bot_state['running'],
        'manual_override': bot_state.get('manual_override', False),
        'is_trading_hours': is_trading_hours,
        'current_time': now.isoformat(),
        'next_scan': 'In progress' if (is_trading_hours and bot_state['running']) else 'Paused'
    })


# ============================================
# CONTROL DEL BOT
# ============================================

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Inicia el bot manualmente"""
    try:
        bot_controller.start_bot()
        return jsonify({
            'success': True,
            'message': 'Bot iniciado correctamente',
            'status': 'running'
        })
    except Exception as e:
        logger.error(f"Error iniciando bot: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Detiene el bot manualmente"""
    try:
        bot_controller.stop_bot()
        return jsonify({
            'success': True,
            'message': 'Bot detenido correctamente',
            'status': 'stopped'
        })
    except Exception as e:
        logger.error(f"Error deteniendo bot: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============================================
# EXPORT DE DATOS
# ============================================

@app.route('/api/export/trades')
def export_trades():
    """Exporta historial de trades a CSV"""
    try:
        # Buscar archivo de log de trades
        log_file = 'trades_history.csv'
        
        if os.path.exists(log_file):
            return send_file(
                log_file,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'trades_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )
        else:
            # Si no existe, crear uno con posiciones actuales
            api = get_api_client()
            if not api:
                return jsonify({'error': 'No autenticado'}), 401
            
            positions = api.get_positions()
            if not positions:
                return jsonify({'error': 'No hay datos para exportar'}), 404
            
            # Crear DataFrame temporal
            data = []
            for pos in positions:
                pos_data = pos.get('position', {})
                market_data = pos.get('market', {})
                data.append({
                    'Epic': market_data.get('epic', 'Unknown'),
                    'Direction': pos_data.get('direction'),
                    'Size': pos_data.get('size'),
                    'Entry Price': pos_data.get('level'),
                    'Stop Loss': pos_data.get('stopLevel'),
                    'Take Profit': pos_data.get('limitLevel', 0),
                    'Created Date': pos_data.get('createdDate'),
                    'Deal ID': pos_data.get('dealId')
                })
            
            df = pd.DataFrame(data)
            temp_file = f'temp_trades_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            df.to_csv(temp_file, index=False)
            
            return send_file(
                temp_file,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'current_positions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )
    
    except Exception as e:
        logger.error(f"Error exportando trades: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/backtest')
def export_backtest():
    """Exporta resultados de backtesting"""
    try:
        backtest_file = 'backtest_results.csv'
        
        if not os.path.exists(backtest_file):
            return jsonify({'error': 'No hay resultados de backtesting disponibles'}), 404
        
        return send_file(
            backtest_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'backtest_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    except Exception as e:
        logger.error(f"Error exportando backtest: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/logs')
def export_logs():
    """Exporta logs del bot"""
    try:
        log_file = 'intraday_trading_bot.log'
        
        if not os.path.exists(log_file):
            return jsonify({'error': 'No hay logs disponibles'}), 404
        
        return send_file(
            log_file,
            mimetype='text/plain',
            as_attachment=True,
            download_name=f'bot_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
    
    except Exception as e:
        logger.error(f"Error exportando logs: {e}")
        return jsonify({'error': str(e)}), 500


def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """Inicia el servidor del dashboard"""
    logger.info(f"🌐 Dashboard disponible en http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_dashboard(debug=True)