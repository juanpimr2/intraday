"""
Configuración personalizada por activo
Permite tener estrategias y parámetros diferentes para cada instrumento
"""

from typing import Dict, Optional


class AssetConfig:
    """Configuración específica por activo"""
    
    # Configuración por defecto (se aplica a todos los activos que no tengan config específica)
    DEFAULT = {
        'enabled': True,
        'max_margin_percent': 0.35,  # % del balance máximo para este activo
        'sl_percent': 0.08,           # Stop Loss %
        'tp_percent': 0.14,           # Take Profit %
        'min_confidence': 0.50,       # Confianza mínima para operar
        # Indicadores
        'rsi_oversold': 35,
        'rsi_overbought': 70,
        'rsi_period': 14,
        'sma_short': 10,
        'sma_long': 50,
        'min_signals': 2              # Señales mínimas para operar
    }
    
    # Configuraciones específicas por activo
    ASSETS = {
        'GOLD': {
            'enabled': True,
            'max_margin_percent': 0.30,  # Oro más volátil, menos margen
            'sl_percent': 0.06,           # SL más ajustado
            'tp_percent': 0.12,           # TP más conservador
            'min_confidence': 0.55,       # Mayor confianza requerida
            'rsi_oversold': 30,           # Más estricto
            'rsi_overbought': 75,
            'min_signals': 3              # Necesita más confirmación
        },
        'TSLA': {
            'enabled': True,
            'max_margin_percent': 0.25,  # Tesla muy volátil
            'sl_percent': 0.10,           # SL más amplio (gaps)
            'tp_percent': 0.18,           # TP más amplio
            'min_confidence': 0.60,       # Alta confianza necesaria
            'rsi_oversold': 25,
            'rsi_overbought': 80,
            'sma_short': 8,               # Más rápido
            'sma_long': 40,
            'min_signals': 3
        },
        'DE40': {
            'enabled': True,
            'max_margin_percent': 0.40,  # Índice más estable
            'sl_percent': 0.07,
            'tp_percent': 0.12,
            'min_confidence': 0.50,
            'rsi_oversold': 35,
            'rsi_overbought': 70,
            'min_signals': 2
        },
        'SP35': {
            'enabled': True,
            'max_margin_percent': 0.35,  # S&P 500
            'sl_percent': 0.08,
            'tp_percent': 0.14,
            'min_confidence': 0.50,
            'rsi_oversold': 35,
            'rsi_overbought': 70,
            'min_signals': 2
        }
    }
    
    @classmethod
    def get_config(cls, epic: str) -> Dict:
        """
        Obtiene la configuración para un activo específico
        
        Args:
            epic: Identificador del activo
            
        Returns:
            Dict con configuración (mezcla default + específica)
        """
        # Empezar con configuración default
        config = cls.DEFAULT.copy()
        
        # Sobrescribir con configuración específica si existe
        if epic in cls.ASSETS:
            asset_specific = cls.ASSETS[epic]
            config.update(asset_specific)
        
        return config
    
    @classmethod
    def is_enabled(cls, epic: str) -> bool:
        """Verifica si un activo está habilitado para trading"""
        config = cls.get_config(epic)
        return config.get('enabled', True)
    
    @classmethod
    def get_sl_percent(cls, epic: str, direction: str) -> float:
        """Obtiene el % de Stop Loss para un activo"""
        config = cls.get_config(epic)
        return config.get('sl_percent', 0.08)
    
    @classmethod
    def get_tp_percent(cls, epic: str, direction: str) -> float:
        """Obtiene el % de Take Profit para un activo"""
        config = cls.get_config(epic)
        return config.get('tp_percent', 0.14)
    
    @classmethod
    def get_max_margin_percent(cls, epic: str) -> float:
        """Obtiene el % máximo de margen para un activo"""
        config = cls.get_config(epic)
        return config.get('max_margin_percent', 0.35)
    
    @classmethod
    def get_indicator_params(cls, epic: str) -> Dict:
        """Obtiene parámetros de indicadores para un activo"""
        config = cls.get_config(epic)
        return {
            'rsi_oversold': config.get('rsi_oversold', 35),
            'rsi_overbought': config.get('rsi_overbought', 70),
            'rsi_period': config.get('rsi_period', 14),
            'sma_short': config.get('sma_short', 10),
            'sma_long': config.get('sma_long', 50),
            'min_signals': config.get('min_signals', 2),
            'min_confidence': config.get('min_confidence', 0.50)
        }
    
    @classmethod
    def add_asset(cls, epic: str, config: Optional[Dict] = None):
        """
        Añade un nuevo activo al trading
        
        Args:
            epic: Identificador del activo (ej: 'AAPL', 'EURUSD')
            config: Configuración específica (opcional, usa DEFAULT si no se proporciona)
        """
        if config is None:
            config = cls.DEFAULT.copy()
        
        cls.ASSETS[epic] = config
    
    @classmethod
    def remove_asset(cls, epic: str):
        """Elimina un activo del trading (lo deshabilita)"""
        if epic in cls.ASSETS:
            cls.ASSETS[epic]['enabled'] = False
    
    @classmethod
    def get_enabled_assets(cls) -> list:
        """Obtiene lista de activos habilitados"""
        return [epic for epic in cls.ASSETS.keys() if cls.is_enabled(epic)]


# Ejemplo de uso:
# AssetConfig.add_asset('AAPL', {
#     'enabled': True,
#     'sl_percent': 0.08,
#     'tp_percent': 0.15,
#     'min_confidence': 0.55
# })