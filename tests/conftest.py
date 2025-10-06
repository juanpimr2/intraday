"""
Configuración de fixtures para tests
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_api_client():
    """Mock del cliente API de Capital.com"""
    client = Mock()
    
    # Mock authenticate
    client.authenticate.return_value = True
    
    # Mock get_account_info
    client.get_account_info.return_value = {
        'balance': {
            'balance': 10000.0,
            'available': 8500.0
        },
        'accountId': 'TEST123'
    }
    
    # Mock get_positions
    client.get_positions.return_value = [
        {
            'position': {
                'epic': 'GOLD',
                'direction': 'BUY',
                'size': 0.5,
                'level': 1950.0,
                'stopLevel': 1900.0,
                'limitLevel': 2000.0,
                'currency': 'EUR',
                'createdDate': '2024-01-01T10:00:00',
                'dealId': 'DEAL001'
            },
            'market': {
                'instrumentName': 'Gold'
            }
        }
    ]
    
    # Mock get_market_data
    client.get_market_data.return_value = {
        'prices': [
            {
                'snapshotTime': '2024-01-01T09:00:00',
                'closePrice': 1940.0,
                'openPrice': 1935.0,
                'highPrice': 1945.0,
                'lowPrice': 1930.0
            },
            {
                'snapshotTime': '2024-01-01T10:00:00',
                'closePrice': 1950.0,
                'openPrice': 1940.0,
                'highPrice': 1955.0,
                'lowPrice': 1938.0
            }
        ]
    }
    
    return client


@pytest.fixture
def flask_client():
    """Cliente de prueba para Flask"""
    from dashboard.app import app
    
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        yield client