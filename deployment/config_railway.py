# config_railway.py
"""
Configuración para deployment en Railway
"""
import os

class RailwayConfig:
    # PostgreSQL desde Railway
    POSTGRES_HOST = os.getenv('PGHOST', 'localhost')
    POSTGRES_PORT = os.getenv('PGPORT', 5432)
    POSTGRES_DB = os.getenv('PGDATABASE', 'trading_bot')
    POSTGRES_USER = os.getenv('PGUSER', 'trader')
    POSTGRES_PASSWORD = os.getenv('PGPASSWORD', 'secure_password_123')
    
    # Capital.com API
    CAPITAL_API_KEY = os.getenv('CAPITAL_API_KEY')
    CAPITAL_PASSWORD = os.getenv('CAPITAL_PASSWORD')
    CAPITAL_EMAIL = os.getenv('CAPITAL_EMAIL')
    
    # Puerto para Flask
    PORT = int(os.getenv('PORT', 5000))
