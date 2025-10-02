"""
Cliente para la API de Capital.com
"""

import requests
import logging
from typing import Dict, Optional
from config import Config

logger = logging.getLogger(__name__)


class CapitalClient:
    """Cliente para interactuar con la API de Capital.com"""
    
    def __init__(self):
        self.session = requests.Session()
        self.cst = None
        self.x_security_token = None
        self.base_url = Config.BASE_URL
        
    def authenticate(self) -> bool:
        """
        Autentica con la API de Capital.com
        
        Returns:
            bool: True si la autenticación fue exitosa
        """
        try:
            url = f"{self.base_url}/api/v1/session"
            headers = {
                "X-CAP-API-KEY": Config.API_KEY,
                "Content-Type": "application/json"
            }
            data = {
                "identifier": Config.EMAIL,
                "password": Config.PASSWORD
            }
            
            logger.info("Autenticando con Capital.com...")
            response = self.session.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                self.cst = response.headers.get('CST')
                self.x_security_token = response.headers.get('X-SECURITY-TOKEN')
                
                # Actualizar headers de la sesión
                self.session.headers.update({
                    'X-SECURITY-TOKEN': self.x_security_token,
                    'CST': self.cst,
                    'Content-Type': 'application/json'
                })
                
                logger.info("✅ Autenticación exitosa")
                return True
            else:
                logger.error(f"❌ Error autenticación: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en autenticación: {e}")
            return False
    
    def get_account_info(self) -> Dict:
        """
        Obtiene información de la cuenta
        
        Returns:
            Dict: Información de la cuenta
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/accounts")
            
            if response.status_code == 200:
                data = response.json()
                if 'accounts' in data and data['accounts']:
                    account = data['accounts'][0]
                    return account
            return {}
            
        except Exception as e:
            logger.error(f"Error obteniendo cuenta: {e}")
            return {}
    
    def get_market_data(self, epic: str, resolution: str, max_values: int = 200) -> Dict:
        """
        Obtiene datos de mercado para un activo
        
        Args:
            epic: Identificador del activo
            resolution: Resolución temporal (HOUR, DAY, etc)
            max_values: Número máximo de valores a obtener
            
        Returns:
            Dict: Datos de mercado
        """
        try:
            params = {
                'resolution': resolution,
                'max': max_values
            }
            response = self.session.get(
                f"{self.base_url}/api/v1/prices/{epic}",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            return {}
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de {epic}: {e}")
            return {}
    
    def get_market_details(self, epic: str) -> Dict:
        """
        Obtiene detalles del mercado (leverage, marginRate, etc)
        
        Args:
            epic: Identificador del activo
            
        Returns:
            Dict: Detalles del mercado
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/markets/{epic}")
            
            if response.status_code == 200:
                return response.json()
            return {}
            
        except Exception as e:
            logger.error(f"Error obteniendo detalles de {epic}: {e}")
            return {}
    
    def get_positions(self) -> list:
        """
        Obtiene las posiciones abiertas
        
        Returns:
            list: Lista de posiciones
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/positions")
            
            if response.status_code == 200:
                return response.json().get('positions', [])
            return []
            
        except Exception as e:
            logger.error(f"Error obteniendo posiciones: {e}")
            return []
    
    def place_order(self, order_data: Dict) -> Optional[Dict]:
        """
        Coloca una orden
        
        Args:
            order_data: Datos de la orden
            
        Returns:
            Dict: Respuesta de la orden o None si falla
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/positions",
                json=order_data
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Error colocando orden {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error colocando orden: {e}")
            return None
    
    def close_session(self):
        """Cierra la sesión con la API"""
        try:
            self.session.delete(f"{self.base_url}/api/v1/session")
            logger.info("Sesión cerrada")
        except:
            pass