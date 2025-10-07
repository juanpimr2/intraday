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
    # GESTIÓN DE CAPITAL - CONFIGURACIÓN COMPLETA
    # ============================================
    
    # CONFIGURACIÓN ANTERIOR (para compatibilidad con dashboard)
    TARGET_PERCENT_OF_AVAILABLE = 0.60  # 40% del margen DISPONIBLE para todas las operaciones
    
    # NUEVA CONFIGURACIÓN
    # Modo de capital máximo: 'PERCENTAGE' o 'FIXED'
    CAPITAL_MODE = 'PERCENTAGE'  # Cambiar a 'FIXED' para usar monto fijo

    # Si CAPITAL_MODE = 'PERCENTAGE':
    MAX_CAPITAL_PERCENT = 40.0  # % del balance disponible para TODAS las operaciones juntas

    # Si CAPITAL_MODE = 'FIXED':
    MAX_CAPITAL_FIXED = 400.0   # Monto fijo en EUR para TODAS las operaciones juntas

    # Distribución entre operaciones
    # 'EQUAL' = dividir equitativamente
    # 'WEIGHTED' = por confianza (más confianza = más capital)
    DISTRIBUTION_MODE = 'EQUAL'

    # Margen de seguridad al calcular tamaños (para evitar exceder límites)
    SIZE_SAFETY_MARGIN = 0.85  # Usar solo 85% del tamaño calculado

    # Límites generales
    MAX_CAPITAL_RISK = 0.70              # % del balance como margen total máximo (límite seguridad)
    MAX_MARGIN_PER_ASSET = 0.35          # % del balance máximo por mismo instrumento
    MAX_POSITIONS = 8                     # Número máximo de posiciones simultáneas
    MIN_POSITION_SIZE = 0.01             # Tamaño mínimo de posición
    
    # ============================================
    # STOP LOSS / TAKE PROFIT
    # ============================================
    # MODO: 'STATIC' o 'DYNAMIC'
    # STATIC = usa porcentajes fijos
    # DYNAMIC = usa ATR para calcular SL/TP adaptativos
    SL_TP_MODE = 'STATIC'  # Cambiado a STATIC por defecto para estabilidad
    
    # Operaciones BUY (Compra) - MODO STATIC
    TAKE_PROFIT_PERCENT_BUY = 0.14   # 14% ganancia
    STOP_LOSS_PERCENT_BUY = 0.08     # 8% pérdida
    
    # Operaciones SELL (Venta) - MODO STATIC
    TAKE_PROFIT_PERCENT_SELL = 0.12  # 12% ganancia
    STOP_LOSS_PERCENT_SELL = 0.07    # 7% pérdida
    
    # SL/TP dinámicos basados en ATR - MODO DYNAMIC
    ATR_MULTIPLIER_SL = 2.0     # Multiplicador ATR para Stop Loss
    ATR_MULTIPLIER_TP = 3.0     # Multiplicador ATR para Take Profit
    
    # ============================================
    # UNIVERSO DE ACTIVOS Y HORARIOS
    # ============================================
    ASSETS = ["GOLD", "TSLA", "DE40", "SP35"]
    START_HOUR = 9                    # Hora de inicio de trading
    END_HOUR = 22                     # Hora de fin de trading
    SCAN_INTERVAL = 900               # Intervalo de escaneo en segundos (15 min)
    
    # ============================================
    # MÚLTIPLES TIMEFRAMES (MTF)
    # ============================================
    ENABLE_MTF = False              # Desactivado por defecto para simplicidad
    TIMEFRAME_FAST = "HOUR"         # Timeframe para señales de entrada
    TIMEFRAME_SLOW = "HOUR_4"       # Timeframe para confirmar tendencia (HOUR_4, DAY)
    TIMEFRAME = TIMEFRAME_FAST      # Para compatibilidad con código existente
    
    # ============================================
    # FILTROS DE VOLATILIDAD (ATR)
    # ============================================
    MIN_ATR_PERCENT = 0.5       # % mínimo de volatilidad para operar
    MAX_ATR_PERCENT = 5.0       # % máximo (evitar pánico/noticias)
    OPTIMAL_ATR_MIN = 1.0       # Sweet spot mínimo
    OPTIMAL_ATR_MAX = 3.0       # Sweet spot máximo
    ATR_PERIOD = 14             # Período del ATR
    
    # ============================================
    # FILTROS DE TENDENCIA (ADX)
    # ============================================
    ENABLE_ADX_FILTER = False       # Desactivado por defecto para simplicidad
    MIN_ADX_TREND = 20.0            # ADX mínimo para considerar tendencia
    STRONG_ADX_THRESHOLD = 40.0     # ADX fuerte (boost de confianza)
    ADX_PERIOD = 14                 # Período del ADX
    
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

    # Circuit Breaker - Protección contra pérdidas excesivas
    ENABLE_CIRCUIT_BREAKER = True

    # Límites de pérdida
    MAX_DAILY_LOSS_PERCENT = 3.0      # -3% del capital en un día
    MAX_WEEKLY_LOSS_PERCENT = 8.0     # -8% del capital en la semana
    MAX_CONSECUTIVE_LOSSES = 5         # 5 trades perdedores seguidos
    MAX_TOTAL_DRAWDOWN_PERCENT = 15.0 # -15% desde máximo histórico

    # Acciones al activarse
    CIRCUIT_BREAKER_ACTION = 'PAUSE'   # 'PAUSE' o 'STOP'
    
    # ============================================
    # DISTRIBUCIÓN DE CAPITAL DIARIO (TAREA 5)
    # ============================================
    
    # Días de trading por semana (Lunes a Viernes)
    TRADING_DAYS_PER_WEEK = 5
    
    # Modo de distribución diaria
    # True = Divide capital semanal en días (recomendado)
    # False = Usa todo el capital disponible sin límite diario
    ENABLE_DAILY_CAPITAL_LIMIT = True


class TradingMode:
    """Modos de trading disponibles"""
    DEMO = "demo"
    LIVE = "live"
    
    # Modo actual
    CURRENT = DEMO