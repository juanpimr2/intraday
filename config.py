"""
Configuración centralizada del bot de trading
"""

import os

class Config:
    """Configuración del bot de trading"""
    
    # ============================================
    # CREDENCIALES API
    # ============================================
    API_KEY = os.getenv('CAPITAL_API_KEY', 'MBnb7mcX81ERKXwM')
    PASSWORD = os.getenv('CAPITAL_PASSWORD', 'Kamikaze.58')
    EMAIL = os.getenv('CAPITAL_EMAIL', 'juanpablomore58@gmail.com')
    BASE_URL = "https://demo-api-capital.backend-capital.com"
    
    # ============================================
    # GESTIÓN DE CAPITAL
    # ============================================
    TARGET_PERCENT_OF_AVAILABLE = 0.40  # % del margen DISPONIBLE para todas las operaciones
    MAX_CAPITAL_RISK = 0.70              # % del balance como margen total máximo (límite seguridad)
    MAX_MARGIN_PER_ASSET = 0.35          # % del balance máximo por mismo instrumento
    MAX_POSITIONS = 3                     # Número máximo de posiciones simultáneas
    MIN_POSITION_SIZE = 0.01             # Tamaño mínimo de posición
    
    # ============================================
    # STOP LOSS / TAKE PROFIT
    # ============================================
    # Operaciones BUY (Compra)
    TAKE_PROFIT_PERCENT_BUY = 0.14   # 14% ganancia
    STOP_LOSS_PERCENT_BUY = 0.08     # 8% pérdida
    
    # Operaciones SELL (Venta)
    TAKE_PROFIT_PERCENT_SELL = 0.12  # 12% ganancia
    STOP_LOSS_PERCENT_SELL = 0.07    # 7% pérdida
    
    # ============================================
    # UNIVERSO DE ACTIVOS Y HORARIOS
    # ============================================
    ASSETS = ["GOLD", "TSLA", "DE40", "SP35"]
    TIMEFRAME = "HOUR"                # Timeframe para análisis
    START_HOUR = 9                    # Hora de inicio de trading
    END_HOUR = 22                     # Hora de fin de trading
    SCAN_INTERVAL = 900               # Intervalo de escaneo en segundos (15 min)
    
    # ============================================
    # PARÁMETROS DE INDICADORES TÉCNICOS
    # ============================================
    # RSI
    RSI_OVERSOLD = 35       # Umbral de sobreventa
    RSI_OVERBOUGHT = 70     # Umbral de sobrecompra
    RSI_PERIOD = 14         # Período del RSI
    
    # MACD
    MACD_FAST = 12          # Período rápido
    MACD_SLOW = 26          # Período lento
    MACD_SIGNAL = 9         # Período de la señal
    
    # SMA (Simple Moving Average)
    SMA_SHORT = 10          # Media móvil corta
    SMA_LONG = 50           # Media móvil larga
    
    # ============================================
    # PARÁMETROS DE SEÑALES
    # ============================================
    MIN_SIGNALS_TO_TRADE = 2    # Mínimo de señales para operar
    MIN_CONFIDENCE = 0.50       # Confianza mínima para ejecutar (50%)


class TradingMode:
    """Modos de trading disponibles"""
    DEMO = "demo"
    LIVE = "live"
    
    # Modo actual
    CURRENT = DEMO