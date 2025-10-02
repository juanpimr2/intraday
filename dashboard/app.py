"""
Dashboard web para monitorear el bot de trading
"""

from flask import Flask, render_template, jsonify
import logging
from datetime import datetime
from api.capital_client import CapitalClient
from config import Config
from utils.helpers import safe_float

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Cliente API global
api_client = None


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
        market = pos.get('market', {})
        
        formatted_positions.append({
            'epic': position_data.get('epic', 'Unknown'),
            'direction': position_data.get('direction', 'Unknown'),
            'size': safe_float(position_data.get('size', 0)),
            'level': safe_float(position_data.get('level', 0)),
            'currency': position_data.get('currency', 'EUR'),
            'createdDate': position_data.get('createdDate', ''),
            'stopLevel': safe_float(position_data.get('stopLevel', 0)),
            'limitLevel': safe_float(position_data.get('limitLevel', 0)),
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
    
    return jsonify({
        'status': 'running',
        'is_trading_hours': is_trading_hours,
        'current_time': now.isoformat(),
        'next_scan': 'In progress' if is_trading_hours else 'Waiting for trading hours'
    })


def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """Inicia el servidor del dashboard"""
    logger.info(f"🌐 Dashboard disponible en http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_dashboard(debug=True)