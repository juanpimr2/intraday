import threading
from trading.trading_bot import TradingBot
from dashboard.app import run_dashboard

def run_bot():
    bot = TradingBot()
    bot.run()

def run_web():
    run_dashboard(port=5000)

if __name__ == '__main__':
    # Iniciar dashboard en thread separado
    dashboard_thread = threading.Thread(target=run_web, daemon=True)
    dashboard_thread.start()
    
    # Ejecutar bot en thread principal
    run_bot()