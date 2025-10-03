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
    """Endpoint para obtener posiciones abiertas - MEJORADO"""
    api = get_api_client()
    if not api:
        return jsonify({'error': 'No autenticado'}), 401
    
    positions = api.get_positions()
    
    # 🔍 DEBUG: Log de la estructura completa (primera posición)
    if positions:
        logger.info("="*60)
        logger.info("📋 DEBUG: Estructura de posición de la API")
        logger.info("="*60)
        import json
        logger.info(json.dumps(positions[0], indent=2, default=str))
        logger.info("="*60)
    
    formatted_positions = []
    for pos in positions:
        position_data = pos.get('position', {})
        market_data = pos.get('market', {})
        
        # ============================================
        # EPIC - Buscar en TODOS los lugares posibles
        # ============================================
        epic = None
        
        # Opción 1: market.epic
        if 'epic' in market_data and market_data['epic']:
            epic = market_data['epic']
            logger.debug(f"Epic encontrado en market.epic: {epic}")
        
        # Opción 2: market.instrumentName
        elif 'instrumentName' in market_data and market_data['instrumentName']:
            epic = market_data['instrumentName']
            logger.debug(f"Epic encontrado en market.instrumentName: {epic}")
        
        # Opción 3: position.epic
        elif 'epic' in position_data and position_data['epic']:
            epic = position_data['epic']
            logger.debug(f"Epic encontrado en position.epic: {epic}")
        
        # Opción 4: position.instrumentName
        elif 'instrumentName' in position_data and position_data['instrumentName']:
            epic = position_data['instrumentName']
            logger.debug(f"Epic encontrado en position.instrumentName: {epic}")
        
        # Opción 5: Buscar en el root
        elif 'epic' in pos and pos['epic']:
            epic = pos['epic']
            logger.debug(f"Epic encontrado en root: {epic}")
        
        # Si no se encuentra, usar 'Unknown' pero loggear
        if not epic:
            epic = 'Unknown'
            logger.warning(f"⚠️  Epic no encontrado. Position data keys: {list(position_data.keys())}")
            logger.warning(f"⚠️  Market data keys: {list(market_data.keys())}")
        
        # ============================================
        # TAKE PROFIT (limitLevel) - Buscar en todos los lugares
        # ============================================
        limit_level = 0.0
        
        # Opción 1: position.limitLevel
        if position_data.get('limitLevel'):
            limit_level = safe_float(position_data.get('limitLevel'))
            logger.debug(f"TP encontrado en position.limitLevel: {limit_level}")
        
        # Opción 2: position.profitLevel
        elif position_data.get('profitLevel'):
            limit_level = safe_float(position_data.get('profitLevel'))
            logger.debug(f"TP encontrado en position.profitLevel: {limit_level}")
        
        # Opción 3: position.limit.level (estructura anidada)
        elif 'limit' in position_data and isinstance(position_data['limit'], dict):
            if 'level' in position_data['limit']:
                limit_level = safe_float(position_data['limit']['level'])
                logger.debug(f"TP encontrado en position.limit.level: {limit_level}")
        
        # Opción 4: position.limitPrice
        elif position_data.get('limitPrice'):
            limit_level = safe_float(position_data.get('limitPrice'))
            logger.debug(f"TP encontrado en position.limitPrice: {limit_level}")
        
        # Opción 5: position.takeProfit
        elif position_data.get('takeProfit'):
            limit_level = safe_float(position_data.get('takeProfit'))
            logger.debug(f"TP encontrado en position.takeProfit: {limit_level}")
        
        # Si no se encuentra, loggear
        if limit_level == 0.0:
            logger.warning(f"⚠️  Take Profit no encontrado para {epic}")
            logger.warning(f"⚠️  Position data keys: {list(position_data.keys())}")
        
        # ============================================
        # Formatear posición
        # ============================================
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
    try:
        return jsonify({
            'assets': Config.ASSETS,
            'max_positions': Config.MAX_POSITIONS,
            'target_percent': getattr(Config, 'TARGET_PERCENT_OF_AVAILABLE', 0.40) * 100,
            'max_risk': getattr(Config, 'MAX_CAPITAL_RISK', 0.70) * 100,
            'timeframe': Config.TIMEFRAME,
            'trading_hours': f"{Config.START_HOUR}:00 - {Config.END_HOUR}:00"
        })
    except Exception as e:
        logger.error(f"Error en get_config: {e}")
        return jsonify({
            'assets': [],
            'max_positions': 0,
            'target_percent': 0,
            'max_risk': 0,
            'timeframe': 'HOUR',
            'trading_hours': '9:00 - 22:00'
        }), 200


@app.route('/api/config/capital', methods=['GET'])
def get_capital_config():
    """Obtiene configuración de capital"""
    try:
        return jsonify({
            'capital_mode': Config.CAPITAL_MODE,
            'max_capital_percent': Config.MAX_CAPITAL_PERCENT,
            'max_capital_fixed': Config.MAX_CAPITAL_FIXED,
            'distribution_mode': Config.DISTRIBUTION_MODE
        })
    except Exception as e:
        logger.error(f"Error en get_capital_config: {e}")
        return jsonify({
            'capital_mode': 'PERCENTAGE',
            'max_capital_percent': 40.0,
            'max_capital_fixed': 400.0,
            'distribution_mode': 'EQUAL'
        }), 200


@app.route('/api/config/capital', methods=['POST'])
def update_capital_config():
    """Actualiza configuración de capital""" 
    try:
        data = request.get_json()
        
        # Validar y actualizar CAPITAL_MODE
        if 'capital_mode' in data:
            mode = data['capital_mode'].upper()
            if mode in ['PERCENTAGE', 'FIXED']:
                Config.CAPITAL_MODE = mode
                logger.info(f"✅ Modo de capital actualizado: {mode}")
            else:
                return jsonify({'error': 'Modo inválido. Usar PERCENTAGE o FIXED'}), 400
        
        # Actualizar MAX_CAPITAL_PERCENT
        if 'max_capital_percent' in data:
            percent = float(data['max_capital_percent'])
            if 1 <= percent <= 100:
                Config.MAX_CAPITAL_PERCENT = percent
                logger.info(f"✅ Porcentaje máximo actualizado: {percent}%")
            else:
                return jsonify({'error': 'Porcentaje debe estar entre 1 y 100'}), 400
        
        # Actualizar MAX_CAPITAL_FIXED
        if 'max_capital_fixed' in data:
            fixed = float(data['max_capital_fixed'])
            if fixed > 0:
                Config.MAX_CAPITAL_FIXED = fixed
                logger.info(f"✅ Monto fijo actualizado: €{fixed:.2f}")
            else:
                return jsonify({'error': 'Monto debe ser mayor a 0'}), 400
        
        # Actualizar DISTRIBUTION_MODE
        if 'distribution_mode' in data:
            dist_mode = data['distribution_mode'].upper()
            if dist_mode in ['EQUAL', 'WEIGHTED']:
                Config.DISTRIBUTION_MODE = dist_mode
                logger.info(f"✅ Modo de distribución actualizado: {dist_mode}")
            else:
                return jsonify({'error': 'Modo inválido. Usar EQUAL o WEIGHTED'}), 400
        
        return jsonify({
            'success': True,
            'message': 'Configuración actualizada correctamente',
            'config': {
                'capital_mode': Config.CAPITAL_MODE,
                'max_capital_percent': Config.MAX_CAPITAL_PERCENT,
                'max_capital_fixed': Config.MAX_CAPITAL_FIXED,
                'distribution_mode': Config.DISTRIBUTION_MODE
            }
        })
    
    except Exception as e:
        logger.error(f"Error actualizando configuración: {e}")
        return jsonify({'error': str(e)}), 500


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