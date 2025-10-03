# start_all.py (CORREGIDO)
import threading
from trading.trading_bot import TradingBot
from dashboard.app import run_dashboard

def run_bot_thread(bot):
    """Ejecuta el bot en un thread"""
    bot.run()

def run_dashboard_thread():
    """Ejecuta el dashboard"""
    run_dashboard(port=5000)  # ✅ Sin pasar el bot

if __name__ == '__main__':
    # Crear instancia del bot
    bot = TradingBot()
    
    # Iniciar dashboard en thread separado
    dashboard_thread = threading.Thread(target=run_dashboard_thread, daemon=True)
    dashboard_thread.start()
    
    # Ejecutar bot en thread principal
    run_bot_thread(bot)