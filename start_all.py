import threading
from trading.trading_bot import TradingBot
from dashboard.app import run_dashboard

def run_bot_thread(bot):
    """Ejecuta el bot en un thread"""
    bot.run()

def run_dashboard_thread(bot):
    """Ejecuta el dashboard pasándole la instancia del bot"""
    run_dashboard(bot, port=5000)

if __name__ == '__main__':
    # Crear instancia única del bot
    bot = TradingBot()
    
    # Iniciar dashboard en thread separado (con acceso al bot)
    dashboard_thread = threading.Thread(target=run_dashboard_thread, args=(bot,), daemon=True)
    dashboard_thread.start()
    
    # Ejecutar bot en thread principal
    run_bot_thread(bot)