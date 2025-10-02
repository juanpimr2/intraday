"""
Gestor de posiciones y margen
"""

import math
import logging
from typing import Dict, Tuple, List
from config import Config
from utils.helpers import safe_float, looks_like_equity

logger = logging.getLogger(__name__)


class PositionManager:
    """Gestiona posiciones, margen y sizing"""
    
    def __init__(self, api_client):
        self.api = api_client
        self.market_details_cache: Dict[str, Dict] = {}
    
    def get_account_balance(self, account_info: Dict) -> Tuple[float, float]:
        """
        Obtiene balance y disponible de la cuenta
        
        Returns:
            tuple: (balance, disponible)
        """
        balance = safe_float(account_info.get('balance', {}).get('balance', 0))
        available = safe_float(account_info.get('balance', {}).get('available', 0))
        return balance, available
    
    def calculate_margin_used(self, account_info: Dict) -> float:
        """
        Calcula el margen usado (balance - disponible)
        
        Returns:
            float: Margen usado en EUR
        """
        balance, available = self.get_account_balance(account_info)
        return max(balance - available, 0.0)
    
    def get_market_details(self, epic: str) -> Dict:
        """
        Obtiene detalles del mercado (con caché)
        
        Returns:
            Dict con: leverage, marginRate, minSize, stepSize, precision
        """
        if epic in self.market_details_cache:
            return self.market_details_cache[epic]
        
        try:
            data = self.api.get_market_details(epic)
            details = self._parse_market_details(data, epic)
            self.market_details_cache[epic] = details
            return details
        except Exception as e:
            logger.warning(f"Error obteniendo detalles de {epic}: {e}. Usando fallback.")
            return self._fallback_market_details(epic)
    
    def _parse_market_details(self, data: Dict, epic: str) -> Dict:
        """Parsea los detalles del mercado desde la respuesta de la API"""
        
        def deep_search(d, keys):
            """Búsqueda recursiva de keys en dict anidado"""
            if not isinstance(d, dict):
                return None
            for k in keys:
                if k in d and d[k]:
                    return d[k]
            for v in d.values():
                if isinstance(v, dict):
                    result = deep_search(v, keys)
                    if result is not None:
                        return result
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            result = deep_search(item, keys)
                            if result is not None:
                                return result
            return None
        
        details = {}
        details['leverage'] = deep_search(data, ['leverage', 'leverageFactor'])
        margin_rate = deep_search(data, ['marginRate', 'marginFactor'])
        
        try:
            details['marginRate'] = float(margin_rate) if margin_rate is not None else None
        except:
            details['marginRate'] = None
        
        details['minSize'] = safe_float(
            deep_search(data, ['minDealSize', 'minSize']),
            Config.MIN_POSITION_SIZE
        )
        details['stepSize'] = safe_float(
            deep_search(data, ['dealSizeStep', 'stepSize']),
            0.01
        )
        details['precision'] = int(safe_float(
            deep_search(data, ['lotSizePrecision']),
            2
        ))
        
        # Fallback conservador si no hay leverage ni marginRate
        if not details['marginRate'] and not details['leverage']:
            details['marginRate'] = 0.20 if looks_like_equity(epic) else 0.05
        
        return details
    
    def _fallback_market_details(self, epic: str) -> Dict:
        """Detalles de mercado con fallback conservador"""
        return {
            'leverage': None,
            'marginRate': 0.20 if looks_like_equity(epic) else 0.05,
            'minSize': Config.MIN_POSITION_SIZE,
            'stepSize': 0.01,
            'precision': 2
        }
    
    def calculate_margin(self, price: float, size: float, market_details: Dict, epic: str = None) -> float:
        """
        Calcula el margen requerido para una posición
        
        Args:
            price: Precio del activo
            size: Tamaño de la posición
            market_details: Detalles del mercado
            epic: Identificador del activo (opcional, para fallback)
            
        Returns:
            float: Margen requerido en EUR
        """
        price = safe_float(price)
        size = safe_float(size)
        
        leverage = market_details.get('leverage')
        margin_rate = market_details.get('marginRate')
        
        if leverage and leverage > 0:
            return (price * size) / leverage
        if margin_rate and margin_rate > 0:
            return price * size * margin_rate
        
        # Fallback conservador
        fallback_rate = 0.20 if (epic and looks_like_equity(epic)) else 0.05
        return price * size * fallback_rate
    
    def calculate_position_size(self, epic: str, price: float, target_margin: float) -> Tuple[float, Dict, float]:
        """
        Calcula el tamaño de posición para un margen objetivo
        
        Args:
            epic: Identificador del activo
            price: Precio actual
            target_margin: Margen objetivo en EUR
            
        Returns:
            tuple: (size, market_details, estimated_margin)
        """
        price = safe_float(price)
        target_margin = safe_float(target_margin)
        
        details = self.get_market_details(epic)
        
        # Calcular tamaño aproximado
        if details.get('marginRate'):
            size = target_margin / max(price * details['marginRate'], 1e-9)
        elif details.get('leverage'):
            size = (target_margin * details['leverage']) / max(price, 1e-9)
        else:
            margin_rate = 0.20 if looks_like_equity(epic) else 0.05
            size = target_margin / max(price * margin_rate, 1e-9)
        
        # Ajustar al step size
        step = safe_float(details.get('stepSize', 0.01), 0.01)
        min_size = safe_float(details.get('minSize', Config.MIN_POSITION_SIZE))
        precision = int(safe_float(details.get('precision', 2)))
        
        size = math.floor(size / step) * step
        size = max(size, min_size)
        size = round(size, precision)
        
        # Calcular margen estimado con el tamaño ajustado
        margin_est = self.calculate_margin(price, size, details, epic)
        
        return size, details, margin_est
    
    def get_positions(self) -> List[Dict]:
        """Obtiene posiciones actuales"""
        return self.api.get_positions()
    
    def get_margin_by_asset(self) -> Dict[str, float]:
        """
        Calcula el margen usado por cada activo
        
        Returns:
            Dict: {epic: margen_usado}
        """
        margin_by_asset = {}
        
        for position in self.get_positions():
            pos_data = position.get('position') or {}
            epic = pos_data.get('epic') or 'Unknown'
            level = safe_float(pos_data.get('level', 0))
            size = safe_float(pos_data.get('size', 0))
            
            if level <= 0 or size <= 0 or epic == 'Unknown':
                continue
            
            details = self.get_market_details(epic)
            margin = self.calculate_margin(level, size, details, epic)
            margin_by_asset[epic] = margin_by_asset.get(epic, 0.0) + margin
        
        return margin_by_asset
    
    def calculate_stop_loss(self, price: float, direction: str) -> float:
        """Calcula el nivel de stop loss"""
        if direction == 'BUY':
            return round(price * (1 - Config.STOP_LOSS_PERCENT_BUY), 2)
        else:  # SELL
            return round(price * (1 + Config.STOP_LOSS_PERCENT_SELL), 2)
    
    def calculate_take_profit(self, price: float, direction: str) -> float:
        """Calcula el nivel de take profit"""
        if direction == 'BUY':
            return round(price * (1 + Config.TAKE_PROFIT_PERCENT_BUY), 2)
        else:  # SELL
            return round(price * (1 - Config.TAKE_PROFIT_PERCENT_SELL), 2)