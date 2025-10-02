"""
Funciones auxiliares y utilidades
"""

import sys
import io
import re


def setup_console_encoding():
    """Configura encoding UTF-8 para la consola (necesario en Windows)"""
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def safe_float(value, default=0.0) -> float:
    """
    Convierte cualquier valor a float de forma segura
    
    Args:
        value: Valor a convertir (puede ser dict, str, int, float, None)
        default: Valor por defecto si la conversión falla
        
    Returns:
        float: Valor convertido o default
    """
    if value is None:
        return default
    
    if isinstance(value, dict):
        # Si es dict, intenta obtener 'bid' o el primer valor numérico
        if 'bid' in value:
            return safe_float(value['bid'], default)
        if 'ask' in value:
            return safe_float(value['ask'], default)
        
        # Busca el primer valor numérico en el dict
        for v in value.values():
            try:
                return float(v)
            except:
                continue
        return default
    
    try:
        return float(value)
    except:
        return default


def looks_like_equity(epic: str) -> bool:
    """
    Determina si un epic parece ser una acción (equity)
    
    Args:
        epic: Identificador del activo
        
    Returns:
        bool: True si parece ser una acción
    """
    # Tiene letras pero no termina en números
    has_letters = bool(re.search(r'[A-Za-z]{2,}', epic))
    ends_with_numbers = bool(re.search(r'\d{2,}$', epic))
    
    return has_letters and not ends_with_numbers


def format_currency(amount: float, symbol: str = "€") -> str:
    """
    Formatea una cantidad como moneda
    
    Args:
        amount: Cantidad a formatear
        symbol: Símbolo de moneda
        
    Returns:
        str: Cantidad formateada (ej: "€1,234.56")
    """
    return f"{symbol}{amount:,.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Formatea un valor como porcentaje
    
    Args:
        value: Valor decimal (0.15 = 15%)
        decimals: Número de decimales
        
    Returns:
        str: Porcentaje formateado (ej: "15.0%")
    """
    return f"{value * 100:.{decimals}f}%"