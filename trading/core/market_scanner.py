# trading/core/market_scanner.py
"""
Scanner de mercado para identificar oportunidades
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MarketScanner:
    """Escanea mercados buscando oportunidades de trading"""
    
    def __init__(self, api_client, strategy, indicators, config):
        self.api = api_client
        self.strategy = strategy
        self.indicators = indicators
        self.config = config
        self.last_scan = {}
        
    async def scan_assets(self, assets: List[str]) -> List[Dict[str, Any]]:
        """Escanea lista de activos buscando señales"""
        signals = []
        
        for epic in assets:
            try:
                signal = await self.scan_single_asset(epic)
                if signal:
                    signals.append(signal)
                    
            except Exception as e:
                logger.error(f"Error escaneando {epic}: {e}")
                continue
        
        return signals
    
    async def scan_single_asset(self, epic: str) -> Optional[Dict[str, Any]]:
        """Escanea un activo individual"""
        try:
            # Obtener datos históricos
            candles = await self.api.get_prices(
                epic=epic,
                resolution=self.config.TIMEFRAME,
                max_points=100
            )
            
            if not candles or len(candles) < 20:
                return None
            
            # Calcular indicadores
            indicators_data = self.indicators.calculate_all(candles)
            
            # Generar señal usando la estrategia
            signal = self.strategy.generate_signal(epic, indicators_data)
            
            # Validar señal
            if self._validate_signal(signal):
                self.last_scan[epic] = datetime.now()
                return signal
                
        except Exception as e:
            logger.error(f"Error procesando {epic}: {e}")
            
        return None
    
    def _validate_signal(self, signal: Optional[Dict]) -> bool:
        """Valida que una señal cumpla criterios mínimos"""
        if not signal:
            return False
            
        # Verificar confianza mínima
        if signal.get('confidence', 0) < self.config.MIN_CONFIDENCE:
            return False
        
        # Verificar que tenga SL/TP
        if not signal.get('stop_loss') or not signal.get('take_profit'):
            logger.warning(f"Señal sin SL/TP: {signal.get('epic')}")
            return False
        
        # Verificar ratio riesgo/beneficio
        entry = signal.get('entry_price', 0)
        sl = signal.get('stop_loss', 0)
        tp = signal.get('take_profit', 0)
        
        if entry and sl and tp:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            
            if risk > 0:
                rr_ratio = reward / risk
                if rr_ratio < 1.5:  # Mínimo 1.5:1
                    logger.info(f"R:R insuficiente ({rr_ratio:.2f}): {signal.get('epic')}")
                    return False
        
        return True
    
    def get_scan_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del escaneo"""
        return {
            'assets_scanned': len(self.last_scan),
            'last_scan_times': {
                epic: scan_time.isoformat() 
                for epic, scan_time in self.last_scan.items()
            }
        }