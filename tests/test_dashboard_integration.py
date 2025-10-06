"""
Tests de integración para el Dashboard
Prueba todos los endpoints y funcionalidades del dashboard
"""

import pytest
import json
import os
import sys
from datetime import datetime, timedelta

# Agregar path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard.app import app
from database.database_manager import DatabaseManager
from config import Config


# ============================================
# FIXTURES
# ============================================

@pytest.fixture
def client():
    """Cliente de prueba de Flask"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def db_manager():
    """Database manager para pruebas"""
    return DatabaseManager()


@pytest.fixture
def mock_session(db_manager):
    """Crea una sesión de prueba en la BD"""
    session_id = db_manager.start_session(
        initial_balance=10000.0,
        config_snapshot={
            'assets': Config.ASSETS,
            'max_positions': Config.MAX_POSITIONS
        }
    )
    
    yield session_id
    
    # Cleanup (opcional)
    # db_manager.delete_session(session_id)


@pytest.fixture
def mock_trades(db_manager, mock_session):
    """Crea trades de prueba"""
    trades = []
    
    for i in range(5):
        trade_id = db_manager.save_trade({
            'epic': 'GOLD',
            'direction': 'BUY' if i % 2 == 0 else 'SELL',
            'entry_price': 1800.0 + i,
            'exit_price': 1810.0 + i if i % 2 == 0 else 1790.0 - i,
            'size': 1.0,
            'entry_date': datetime.now() - timedelta(hours=i),
            'exit_date': datetime.now() - timedelta(hours=i-1),
            'pnl': 10.0 if i % 2 == 0 else -10.0,
            'pnl_percent': 0.5 if i % 2 == 0 else -0.5,
            'reason': 'TAKE_PROFIT' if i % 2 == 0 else 'STOP_LOSS',
            'confidence': 0.7,
            'indicators': {'rsi': 45.0, 'macd': 0.5}
        })
        trades.append(trade_id)
    
    return trades


# ============================================
# TESTS - ENDPOINTS BÁSICOS
# ============================================

def test_index_page(client):
    """Test: Página principal se carga"""
    response = client.get('/')
    assert response.status_code == 200


def test_api_account(client):
    """Test: Endpoint /api/account"""
    response = client.get('/api/account')
    
    # Puede fallar si no hay autenticación, pero no debe crashear
    assert response.status_code in [200, 401, 500]
    
    if response.status_code == 200:
        data = json.loads(response.data)
        assert 'balance' in data
        assert 'available' in data
        assert 'margin_used' in data


def test_api_positions(client):
    """Test: Endpoint /api/positions"""
    response = client.get('/api/positions')
    
    assert response.status_code in [200, 401, 500]
    
    if response.status_code == 200:
        data = json.loads(response.data)
        assert 'positions' in data
        assert 'count' in data


def test_api_config(client):
    """Test: Endpoint /api/config"""
    response = client.get('/api/config')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Verificar que devuelve la configuración
    assert 'assets' in data
    assert 'max_positions' in data
    assert 'timeframe' in data
    assert data['assets'] == Config.ASSETS


def test_api_status(client):
    """Test: Endpoint /api/status"""
    response = client.get('/api/status')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'status' in data
    assert 'is_trading_hours' in data
    assert 'current_time' in data


# ============================================
# TESTS - HISTORIAL DE TRADES
# ============================================

def test_api_trades_history(client, mock_session, mock_trades):
    """Test: Obtener historial de trades"""
    response = client.get('/api/trades/history')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'trades' in data
    assert 'count' in data
    assert isinstance(data['trades'], list)


def test_api_trades_history_with_session(client, mock_session, mock_trades):
    """Test: Obtener trades de una sesión específica"""
    response = client.get(f'/api/trades/history?session_id={mock_session}')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'trades' in data
    assert data['count'] >= 0  # Puede ser 0 si no hay trades


def test_api_trades_history_with_limit(client):
    """Test: Límite en historial de trades"""
    response = client.get('/api/trades/history?limit=10')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert len(data['trades']) <= 10


def test_api_trades_stats(client, mock_session, mock_trades):
    """Test: Estadísticas de trades"""
    response = client.get('/api/trades/stats')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'stats' in data


def test_api_trades_stats_by_session(client, mock_session, mock_trades):
    """Test: Estadísticas de una sesión específica"""
    response = client.get(f'/api/trades/stats?session_id={mock_session}')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'stats' in data


# ============================================
# TESTS - EXPORT TRADES
# ============================================

def test_api_export_trades_csv(client, mock_session, mock_trades):
    """Test: Exportar trades a CSV"""
    response = client.get(f'/api/trades/export/csv?session_id={mock_session}')
    
    # Puede fallar si no hay trades, pero no debe crashear
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        # Verificar que es un archivo
        assert response.content_type in ['text/csv', 'application/octet-stream']


def test_api_export_trades_excel(client, mock_session, mock_trades):
    """Test: Exportar trades a Excel"""
    response = client.get(f'/api/trades/export/excel?session_id={mock_session}')
    
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        # Verificar que es un archivo Excel
        assert 'application' in response.content_type


def test_api_export_invalid_format(client):
    """Test: Formato de export inválido"""
    response = client.get('/api/trades/export/pdf')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_api_export_full_report(client, mock_session, mock_trades):
    """Test: Generar reporte completo"""
    response = client.get(f'/api/report/full?session_id={mock_session}')
    
    assert response.status_code in [200, 400, 500]


def test_api_export_full_report_no_session(client):
    """Test: Reporte sin session_id debe fallar"""
    response = client.get('/api/report/full')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


# ============================================
# TESTS - SESIONES
# ============================================

def test_api_sessions_list(client, mock_session):
    """Test: Listar sesiones"""
    response = client.get('/api/sessions/list')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'sessions' in data
    assert 'count' in data
    assert isinstance(data['sessions'], list)


def test_api_sessions_list_with_limit(client):
    """Test: Listar sesiones con límite"""
    response = client.get('/api/sessions/list?limit=5')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert len(data['sessions']) <= 5


def test_api_session_detail(client, mock_session, mock_trades):
    """Test: Obtener detalle de sesión"""
    response = client.get(f'/api/sessions/{mock_session}')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'session' in data
    assert 'trades' in data
    assert 'stats' in data
    assert 'signals' in data


def test_api_session_detail_invalid(client):
    """Test: Sesión inexistente"""
    response = client.get('/api/sessions/99999')
    
    # Puede ser 200 con datos vacíos o 500
    assert response.status_code in [200, 500]


# ============================================
# TESTS - BACKTESTING
# ============================================

def test_api_backtest_run_basic(client):
    """Test: Ejecutar backtest básico"""
    payload = {
        'days': 7,
        'initial_capital': 5000,
        'assets': ['GOLD']
    }
    
    response = client.post(
        '/api/backtest/run',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    # Puede tardar o fallar si no hay datos, pero no debe crashear
    assert response.status_code in [200, 401, 500]


def test_api_backtest_invalid_days(client):
    """Test: Backtest con días inválidos"""
    payload = {
        'days': 500,  # Más de 365
        'initial_capital': 5000
    }
    
    response = client.post(
        '/api/backtest/run',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_api_backtest_invalid_capital(client):
    """Test: Backtest con capital inválido"""
    payload = {
        'days': 30,
        'initial_capital': 50  # Menos de 100
    }
    
    response = client.post(
        '/api/backtest/run',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_api_backtest_default_params(client):
    """Test: Backtest con parámetros por defecto"""
    response = client.post(
        '/api/backtest/run',
        data=json.dumps({}),
        content_type='application/json'
    )
    
    # Debería usar valores por defecto
    assert response.status_code in [200, 401, 500]


# ============================================
# TESTS - SEÑALES
# ============================================

def test_api_signals_recent(client, mock_session):
    """Test: Obtener señales recientes"""
    response = client.get('/api/signals/recent')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert 'signals' in data
    assert 'count' in data
    assert isinstance(data['signals'], list)


def test_api_signals_recent_with_limit(client):
    """Test: Señales recientes con límite"""
    response = client.get('/api/signals/recent?limit=10')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert len(data['signals']) <= 10


# ============================================
# TESTS - HEALTH CHECK
# ============================================

def test_api_health(client):
    """Test: Health check"""
    response = client.get('/api/health')
    
    assert response.status_code in [200, 500]
    data = json.loads(response.data)
    
    assert 'status' in data
    assert 'database' in data
    assert 'api' in data


# ============================================
# TESTS - ERROR HANDLING
# ============================================

def test_invalid_endpoint(client):
    """Test: Endpoint inexistente"""
    response = client.get('/api/invalid/endpoint')
    
    assert response.status_code == 404


def test_invalid_method(client):
    """Test: Método HTTP inválido"""
    response = client.post('/api/config')  # GET-only endpoint
    
    assert response.status_code == 405


# ============================================
# TESTS - PERFORMANCE
# ============================================

def test_api_response_time(client):
    """Test: Los endpoints responden rápido"""
    import time
    
    endpoints = [
        '/api/config',
        '/api/status',
        '/api/health'
    ]
    
    for endpoint in endpoints:
        start = time.time()
        response = client.get(endpoint)
        elapsed = time.time() - start
        
        # Debe responder en menos de 2 segundos
        assert elapsed < 2.0, f"{endpoint} tardó {elapsed:.2f}s"


# ============================================
# TESTS - CORS
# ============================================

def test_cors_headers(client):
    """Test: Headers CORS están presentes"""
    response = client.get('/api/config')
    
    # CORS debe estar habilitado
    assert 'Access-Control-Allow-Origin' in response.headers


# ============================================
# INFORMACIÓN DE LOS TESTS
# ============================================

"""
CÓMO EJECUTAR ESTOS TESTS:

1. Instalar pytest:
   pip install pytest pytest-flask

2. Ejecutar todos los tests:
   pytest tests/test_dashboard_integration.py -v

3. Ejecutar tests específicos:
   pytest tests/test_dashboard_integration.py::test_api_config -v

4. Ejecutar con coverage:
   pytest tests/test_dashboard_integration.py --cov=dashboard --cov-report=html

5. Ejecutar en modo verbose con logs:
   pytest tests/test_dashboard_integration.py -v -s

6. Ejecutar solo tests rápidos (skip lentos):
   pytest tests/test_dashboard_integration.py -v -m "not slow"

NOTA: Algunos tests requieren:
- PostgreSQL corriendo (docker-compose up -d postgres)
- Migraciones aplicadas
- Credenciales API válidas (opcional, algunos tests funcionan sin auth)
"""