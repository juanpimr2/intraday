# 🚀 Instalación y Uso del Trading Bot

## 📦 Instalación

### 1. Clonar o descargar el proyecto
```bash
cd "C:\Capital Bot\intraday"
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar credenciales
Edita `config.py` con tus credenciales de Capital.com:
```python
API_KEY = "tu_api_key"
PASSWORD = "tu_password"
EMAIL = "tu_email"
BASE_URL = "https://demo-api-capital.backend-capital.com"  # Demo
```

### 4. Crear archivos necesarios
Los siguientes archivos se crean automáticamente:
- `bot_state.json` - Estado del bot
- `intraday_trading_bot.log` - Logs
- `trades_history.csv` - Historial de trades

---

## 🎮 Uso

### Iniciar Bot + Dashboard (Recomendado)
```bash
python start_all.py
```
Luego abre tu navegador en: `http://localhost:5000`

### Solo Bot (sin dashboard)
```bash
python main.py
```

### Solo Backtesting
```bash
python backtesting/run_backtest.py
```

---

## 🎛️ Dashboard - Funcionalidades

### Controles Principales
- **▶️ Iniciar**: Inicia el bot manualmente
- **⏸️ Pausar**: Pausa el bot manualmente
- **Estado**: Muestra si está operando, pausado o fuera de horario

### Información en Tiempo Real
- **Balance y Margen**: Actualización cada 10 segundos
- **Posiciones Abiertas**: Con SL/TP, entry price, tamaño
- **Configuración**: Activos, horarios, límites

### Exportación de Datos
- **Backtest Results**: Resultados de backtesting histórico
- **Trading History**: Historial de trades (demo/live)
- **Bot Logs**: Logs completos del bot

---

## ⚙️ Configuración Avanzada

### Configuración Global (`config.py`)
```python
TARGET_PERCENT_OF_AVAILABLE = 0.40  # 40% del disponible
MAX_CAPITAL_RISK = 0.70              # 70% margen total máximo
MAX_POSITIONS = 3                     # Máx 3 posiciones simultáneas
START_HOUR = 9                        # 9:00 AM
END_HOUR = 22                         # 10:00 PM
```

### Configuración por Activo (`config_assets.py`)
Personaliza cada activo individualmente:
```python
from config_assets import AssetConfig

# Ver config de un activo
config = AssetConfig.get_config('GOLD')

# Añadir nuevo activo
AssetConfig.add_asset('AAPL', {
    'enabled': True,
    'sl_percent': 0.08,
    'tp_percent': 0.15,
    'min_confidence': 0.55
})

# Deshabilitar un activo
AssetConfig.remove_asset('TSLA')
```

---

## 🔍 Monitoreo

### Ver Logs en Vivo
```bash
tail -f intraday_trading_bot.log
```

### Verificar Estado del Bot
1. Abre el dashboard: `http://localhost:5000`
2. Mira el indicador de estado (🟢/🔴)
3. Revisa posiciones abiertas

---

## 🛑 Detener el Bot

### Desde Dashboard
Click en el botón **⏸️ Pausar**

### Desde Terminal
Presiona `Ctrl+C`

---

## 📊 Backtesting

### Ejecutar Backtest
```bash
python backtesting/run_backtest.py
```

### Resultados
- Se guarda en: `backtest_results.csv`
- Métricas: Win rate, profit factor, drawdown, etc.

### Exportar desde Dashboard
Dashboard → 📤 Export → Backtest Results

---

## ⚠️ Importante

- **Demo primero**: Prueba siempre en cuenta demo antes de real
- **Capital de riesgo**: Solo usa capital que puedas permitirte perder
- **Monitoreo**: Revisa regularmente el dashboard y logs
- **Horarios**: El bot opera de 9:00 a 22:00, lunes a viernes
- **Stop Loss**: Siempre configurado automáticamente

---

## 🔧 Troubleshooting

### Error de autenticación
- Verifica credenciales en `config.py`
- Comprueba que estás usando la URL correcta (demo/live)

### Dashboard no carga
- Verifica que Flask está instalado: `pip install flask`
- Comprueba el puerto 5000 no esté ocupado
- Revisa logs en terminal

### Bot no opera
- Verifica horario de trading (9:00-22:00)
- Comprueba que esté iniciado (botón verde)
- Revisa que haya margen disponible
- Mira los logs: `intraday_trading_bot.log`

---

## 📞 Soporte

Para más información, revisa:
- `README.md` - Documentación principal
- Logs del bot - `intraday_trading_bot.log`
- Contexto del proyecto en el código fuente