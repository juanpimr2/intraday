#!/usr/bin/env python3
"""
Bot Intraday Trading - Modular v6.0
Punto de entrada principal
"""

import signal
import sys
import logging
from trading.trading_bot import TradingBot
from utils.helpers import setup_console_encoding

# Configurar encoding UTF-8 para Windows
setup_console_encoding()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('intraday_trading_bot.log', encoding='utf-8'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Variable global para el bot
bot = None

def signal_handler(signum, frame):
    """Maneja señales de interrupción (Ctrl+C, SIGTERM)"""
    logger.info("Señal de interrupción recibida. Deteniendo bot...")
    if bot:
        bot.stop()
    sys.exit(0)

def main():
    """Función principal"""
    global bot
    
    logger.info("="*60)
    logger.info("BOT INTRADAY TRADING INICIADO")
    logger.info("="*60)
    
    # Registrar manejadores de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Crear e iniciar bot
    bot = TradingBot()
    
    try:
        bot.run()
    except Exception as e:
        logger.error(f"Error crítico: {e}")
        if bot:
            bot.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()