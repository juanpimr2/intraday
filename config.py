# config.py
"""
Configuración centralizada del bot de trading
"""

import os


class Config:
    """Configuración del bot de trading"""

    # ============================================
    # GENERAL / TIMEZONE
    # ============================================
    TIMEZONE = os.getenv("TZ_PRIMARY", "Europe/Madrid")

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
    # Nota: el comentario previo decía 40% pero el valor está en 0.60 (60%).
    TARGET_PERCENT_OF_AVAILABLE = 0.60  # % del margen DISPONIBLE para todas las operaciones

    # NUEVA CONFIGURACIÓN (compatibilidad con tu dashboard/ejecutor en vivo)
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
    MAX_POSITIONS = 8                    # Número máximo de posiciones simultáneas
    MIN_POSITION_SIZE = 0.01             # Tamaño mínimo de posición

    # ============================================
    # SOPORTE PARA CAPITAL TRACKER (Backtesting)
    # ============================================
    # Estos flags son leídos por el motor de backtest unificado (BacktestEngine)
    USE_CAPITAL_TRACKER = True           # Activar asignación diaria y por trade
    DAILY_BUDGET_PCT = 0.08              # 8% del equity por día
    PER_TRADE_CAP_PCT = 0.03             # 3% del equity por trade

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
    START_HOUR = 9                      # Hora de inicio de trading
    END_HOUR = 22                       # Hora de fin de trading
    SCAN_INTERVAL = 900                 # Intervalo de escaneo en segundos (15 min)

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
    MAX_DAILY_LOSS_PERCENT = 3.0       # -3% del capital en un día
    MAX_WEEKLY_LOSS_PERCENT = 8.0      # -8% del capital en la semana
    MAX_CONSECUTIVE_LOSSES = 5         # 5 trades perdedores seguidos
    MAX_TOTAL_DRAWDOWN_PERCENT = 15.0  # -15% desde máximo histórico

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

    # ============================================
    # COSTES DE TRADING (aplicados en post-proceso/backtesting)
    # ============================================
    COMMISSION_PER_TRADE = 0.5           # en EUR por operación (aproximado)
    SPREAD_IN_POINTS_DEFAULT = 0.8       # spread medio
    POINT_VALUE_DEFAULT = 1.0            # valor de 1 punto (ajusta según activo)

    # Overrides por instrumento.
    # Para máxima compatibilidad:
    #  - Claves usadas por el motor/`utils.cost_calculator`:
    #       {"commission": ..., "spread_points": ..., "point_value": ...}
    #  - Se incluyen también alias legacy por si otra parte del código los lee:
    #       {"commission_per_trade": ..., "spread_in_points": ...}
    COST_OVERRIDES = {
        "GOLD": {
            "commission": 0.8,
            "spread_points": 0.3,
            "point_value": 10.0,
            # alias legacy:
            "commission_per_trade": 0.8,
            "spread_in_points": 0.3,
        },
        # Añade aquí otros EPIC/instrumentos si difieren del default…
        # "DE40": {"commission": 0.0, "spread_points": 1.0, "point_value": 1.0},
    }

    # ============================================
    # RÉGIMEN DE MERCADO (filtro para Backtesting)
    # ============================================
    # Activar filtro por régimen (bloquea abrir si el régimen detectado coincide con REGIME_FILTER_BLOCK)
    REGIME_FILTER_ENABLED = True
    REGIME_FILTER_BLOCK = "lateral"     # bloquea laterales

    # Parámetros del detector (ATR% + ADX) usados por utils.market_regime.detect_regime(...)
    # Se mapean a tus parámetros existentes para mantener coherencia:
    REGIME_ATR_PERIOD = ATR_PERIOD                      # 14 por defecto
    REGIME_ADX_THRESHOLD = max(25.0, MIN_ADX_TREND)     # umbral de tendencia (mín. 25)
    REGIME_ATR_PCT = MIN_ATR_PERCENT                    # % de ATR sobre precio para evitar rango estrecho

    # ============================================
    # SESIONES DE MERCADO (para reporte por sesión)
    # Europe/Madrid; prioridad a us_open en solape 15:30–16:00
    # ============================================
    SESSIONS_CET = {
        "eu_open": {"start": "08:00", "end": "12:00"},
        "eu_pm":   {"start": "12:00", "end": "16:00"},
        "us_open": {"start": "15:30", "end": "18:00"},
        "us_pm":   {"start": "18:00", "end": "22:00"},
    }


class TradingMode:
    """Modos de trading disponibles"""
    DEMO = "demo"
    LIVE = "live"

    # Modo actual
    CURRENT = DEMO
