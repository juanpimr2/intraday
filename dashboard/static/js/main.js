// Auto-refresh cada 10 segundos
const REFRESH_INTERVAL = 10000;

// Función para formatear moneda
function formatCurrency(amount) {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: 'EUR'
    }).format(amount);
}

// Función para actualizar timestamp
function updateTimestamp() {
    const now = new Date();
    document.getElementById('last-update').textContent = now.toLocaleTimeString('es-ES');
}

// Función para mostrar notificaciones
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

// Función para actualizar cuenta
async function updateAccount() {
    try {
        const response = await fetch('/api/account');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error:', data.error);
            return;
        }
        
        document.getElementById('balance').textContent = formatCurrency(data.balance);
        document.getElementById('available').textContent = formatCurrency(data.available);
        document.getElementById('margin-used').textContent = formatCurrency(data.margin_used);
        document.getElementById('margin-percent').textContent = data.margin_percent.toFixed(1) + '%';
        
    } catch (error) {
        console.error('Error actualizando cuenta:', error);
    }
}

// Función para actualizar posiciones
async function updatePositions() {
    try {
        const response = await fetch('/api/positions');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error:', data.error);
            return;
        }
        
        document.getElementById('positions-count').textContent = data.count;
        
        const container = document.getElementById('positions-container');
        
        if (data.count === 0) {
            container.innerHTML = '<p class="loading">No hay posiciones abiertas</p>';
            return;
        }
        
        let html = '';
        data.positions.forEach(pos => {
            const directionClass = pos.direction.toLowerCase();
            html += `
                <div class="position-item">
                    <div class="position-header">
                        <span class="position-epic">${pos.epic}</span>
                        <span class="position-direction ${directionClass}">${pos.direction}</span>
                    </div>
                    <div class="position-details">
                        <div><strong>Size:</strong> ${pos.size}</div>
                        <div><strong>Entry:</strong> ${formatCurrency(pos.level)}</div>
                        <div><strong>Stop Loss:</strong> ${pos.stopLevel > 0 ? formatCurrency(pos.stopLevel) : 'N/A'}</div>
                        <div><strong>Take Profit:</strong> ${pos.limitLevel > 0 ? formatCurrency(pos.limitLevel) : 'N/A'}</div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error actualizando posiciones:', error);
    }
}

// Función para actualizar configuración
async function updateConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        const container = document.getElementById('config-container');
        
        const html = `
            <div class="config-item">
                <div class="config-label">Activos</div>
                <div class="config-value">${data.assets.join(', ')}</div>
            </div>
            <div class="config-item">
                <div class="config-label">Posiciones Máximas</div>
                <div class="config-value">${data.max_positions}</div>
            </div>
            <div class="config-item">
                <div class="config-label">% Margen Objetivo</div>
                <div class="config-value">${data.target_percent.toFixed(0)}%</div>
            </div>
            <div class="config-item">
                <div class="config-label">Riesgo Máximo</div>
                <div class="config-value">${data.max_risk.toFixed(0)}%</div>
            </div>
            <div class="config-item">
                <div class="config-label">Timeframe</div>
                <div class="config-value">${data.timeframe}</div>
            </div>
            <div class="config-item">
                <div class="config-label">Horario Trading</div>
                <div class="config-value">${data.trading_hours}</div>
            </div>
        `;
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error actualizando configuración:', error);
    }
}

// Función para actualizar estado
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (data.running) {
            statusDot.className = 'dot online';
            statusText.textContent = data.is_trading_hours ? '🟢 Operando' : '🟡 Esperando horario';
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusDot.className = 'dot offline';
            statusText.textContent = '🔴 Pausado';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
        
    } catch (error) {
        console.error('Error actualizando estado:', error);
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        statusDot.className = 'dot offline';
        statusText.textContent = '🔴 Error de conexión';
    }
}

// ============================================
// CONTROL DEL BOT
// ============================================

async function startBot() {
    try {
        showToast('Iniciando bot...', 'info');
        const response = await fetch('/api/bot/start', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('✅ Bot iniciado correctamente', 'success');
            await updateStatus();
        } else {
            showToast('❌ Error al iniciar bot', 'error');
        }
    } catch (error) {
        console.error('Error iniciando bot:', error);
        showToast('❌ Error de conexión', 'error');
    }
}

async function stopBot() {
    try {
        showToast('Pausando bot...', 'info');
        const response = await fetch('/api/bot/stop', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('⏸️ Bot pausado correctamente', 'success');
            await updateStatus();
        } else {
            showToast('❌ Error al pausar bot', 'error');
        }
    } catch (error) {
        console.error('Error pausando bot:', error);
        showToast('❌ Error de conexión', 'error');
    }
}

// ============================================
// EXPORT DE DATOS
// ============================================

async function exportBacktest() {
    try {
        showToast('Descargando backtest results...', 'info');
        window.location.href = '/api/export/backtest';
    } catch (error) {
        console.error('Error exportando backtest:', error);
        showToast('❌ Error al exportar', 'error');
    }
}

async function exportTrades() {
    try {
        showToast('Descargando trading history...', 'info');
        window.location.href = '/api/export/trades';
    } catch (error) {
        console.error('Error exportando trades:', error);
        showToast('❌ Error al exportar', 'error');
    }
}

async function exportLogs() {
    try {
        showToast('Descargando logs...', 'info');
        window.location.href = '/api/export/logs';
    } catch (error) {
        console.error('Error exportando logs:', error);
        showToast('❌ Error al exportar', 'error');
    }
}

// Función para actualizar todo
async function updateAll() {
    updateTimestamp();
    await Promise.all([
        updateAccount(),
        updatePositions(),
        updateConfig(),
        updateStatus()
    ]);
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    updateAll();
    setInterval(updateAll, REFRESH_INTERVAL);
});