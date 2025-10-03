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

// Función para actualizar posiciones - MEJORADA
async function updatePositions() {
    try {
        const response = await fetch('/api/positions');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error:', data.error);
            showToast('Error obteniendo posiciones', 'error');
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
            
            // ============================================
            // EPIC - Detectar si es "Unknown"
            // ============================================
            let epicDisplay = pos.epic;
            let epicWarning = '';
            
            if (pos.epic === 'Unknown' || !pos.epic) {
                epicDisplay = '⚠️ Unknown';
                epicWarning = '<div class="warning-badge">⚠️ Epic no detectado</div>';
            }
            
            // ============================================
            // TAKE PROFIT - Detectar si falta
            // ============================================
            let tpDisplay = 'N/A';
            let tpWarning = '';
            
            if (pos.limitLevel && pos.limitLevel > 0) {
                tpDisplay = formatCurrency(pos.limitLevel);
            } else {
                tpDisplay = '⚠️ N/A';
                tpWarning = '<span class="text-warning"> (no configurado)</span>';
            }
            
            // ============================================
            // STOP LOSS - Detectar si falta
            // ============================================
            let slDisplay = 'N/A';
            let slWarning = '';
            
            if (pos.stopLevel && pos.stopLevel > 0) {
                slDisplay = formatCurrency(pos.stopLevel);
            } else {
                slDisplay = '⚠️ N/A';
                slWarning = '<span class="text-warning"> (no configurado)</span>';
            }
            
            // ============================================
            // CALCULAR DURACIÓN
            // ============================================
            let durationDisplay = '';
            if (pos.createdDate) {
                try {
                    const created = new Date(pos.createdDate);
                    const now = new Date();
                    const diffMs = now - created;
                    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
                    const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
                    
                    if (diffHours > 0) {
                        durationDisplay = `${diffHours}h ${diffMinutes}m`;
                    } else {
                        durationDisplay = `${diffMinutes}m`;
                    }
                } catch (e) {
                    durationDisplay = 'N/A';
                }
            }
            
            // ============================================
            // RENDERIZAR HTML
            // ============================================
            html += `
                <div class="position-item ${pos.epic === 'Unknown' ? 'position-warning' : ''}">
                    <div class="position-header">
                        <span class="position-epic">${epicDisplay}</span>
                        <span class="position-direction ${directionClass}">${pos.direction}</span>
                    </div>
                    ${epicWarning}
                    <div class="position-details">
                        <div><strong>Size:</strong> ${pos.size}</div>
                        <div><strong>Entry:</strong> ${formatCurrency(pos.level)}</div>
                        <div><strong>Stop Loss:</strong> ${slDisplay}${slWarning}</div>
                        <div><strong>Take Profit:</strong> ${tpDisplay}${tpWarning}</div>
                        ${durationDisplay ? `<div><strong>Duración:</strong> ${durationDisplay}</div>` : ''}
                        ${pos.dealId ? `<div><strong>Deal ID:</strong> ${pos.dealId}</div>` : ''}
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error actualizando posiciones:', error);
        showToast('Error de conexión al obtener posiciones', 'error');
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




// Actualizar vista de configuración de capital
async function updateCapitalConfig() {
    try {
        const response = await fetch('/api/config/capital');
        const data = await response.json();
        
        // Actualizar modo
        document.getElementById('capital-mode-view').textContent = 
            data.capital_mode === 'PERCENTAGE' ? 'Porcentaje' : 'Monto Fijo';
        
        // Mostrar/ocultar según modo
        if (data.capital_mode === 'PERCENTAGE') {
            document.getElementById('percent-view-item').style.display = 'block';
            document.getElementById('fixed-view-item').style.display = 'none';
            document.getElementById('capital-percent-view').textContent = 
                `${data.max_capital_percent.toFixed(1)}%`;
        } else {
            document.getElementById('percent-view-item').style.display = 'none';
            document.getElementById('fixed-view-item').style.display = 'block';
            document.getElementById('capital-fixed-view').textContent = 
                formatCurrency(data.max_capital_fixed);
        }
        
        // Actualizar distribución
        document.getElementById('distribution-mode-view').textContent = 
            data.distribution_mode === 'EQUAL' ? 'Equitativa' : 'Ponderada';
        
    } catch (error) {
        console.error('Error actualizando config de capital:', error);
    }
}

// Mostrar editor de capital
function toggleCapitalEdit() {
    document.getElementById('capital-view').style.display = 'none';
    document.getElementById('capital-edit').style.display = 'block';
    
    // Cargar valores actuales
    loadCurrentCapitalConfig();
}

// Cargar configuración actual en el editor
async function loadCurrentCapitalConfig() {
    try {
        const response = await fetch('/api/config/capital');
        const data = await response.json();
        
        // Establecer valores
        document.getElementById('capital-mode-select').value = data.capital_mode;
        document.getElementById('capital-percent-input').value = data.max_capital_percent;
        document.getElementById('capital-fixed-input').value = data.max_capital_fixed;
        document.getElementById('distribution-mode-select').value = data.distribution_mode;
        
        // Mostrar/ocultar inputs según modo
        toggleCapitalModeInputs();
        
    } catch (error) {
        console.error('Error cargando config:', error);
        showToast('Error cargando configuración', 'error');
    }
}


// Toggle entre inputs de porcentaje y monto fijo
function toggleCapitalModeInputs() {
    const mode = document.getElementById('capital-mode-select').value;
    
    if (mode === 'PERCENTAGE') {
        document.getElementById('percent-input-group').style.display = 'block';
        document.getElementById('fixed-input-group').style.display = 'none';
    } else {
        document.getElementById('percent-input-group').style.display = 'none';
        document.getElementById('fixed-input-group').style.display = 'block';
    }
}


// Guardar configuración de capital
async function saveCapitalConfig() {
    try {
        const mode = document.getElementById('capital-mode-select').value;
        const percent = parseFloat(document.getElementById('capital-percent-input').value);
        const fixed = parseFloat(document.getElementById('capital-fixed-input').value);
        const distribution = document.getElementById('distribution-mode-select').value;
        
        // Validaciones
        if (mode === 'PERCENTAGE' && (percent < 1 || percent > 100)) {
            showToast('El porcentaje debe estar entre 1 y 100', 'error');
            return;
        }
        
        if (mode === 'FIXED' && fixed <= 0) {
            showToast('El monto debe ser mayor a 0', 'error');
            return;
        }
        
        // Enviar actualización
        showToast('Guardando configuración...', 'info');
        
        const response = await fetch('/api/config/capital', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                capital_mode: mode,
                max_capital_percent: percent,
                max_capital_fixed: fixed,
                distribution_mode: distribution
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('✅ Configuración guardada correctamente', 'success');
            
            // Cerrar editor y actualizar vista
            cancelCapitalEdit();
            await updateCapitalConfig();
        } else {
            showToast('❌ Error: ' + data.error, 'error');
        }
        
    } catch (error) {
        console.error('Error guardando config:', error);
        showToast('❌ Error de conexión', 'error');
    }
}

// Cancelar edición
function cancelCapitalEdit() {
    document.getElementById('capital-view').style.display = 'grid';
    document.getElementById('capital-edit').style.display = 'none';
}

// Función para actualizar todo
async function updateAll() {
    updateTimestamp();
    await Promise.all([
        updateAccount(),
        updatePositions(),
        updateConfig(),
        updateCapitalConfig(),  // ← AGREGAR ESTA LÍNEA
        updateStatus()
    ]);
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    updateAll();
    setInterval(updateAll, REFRESH_INTERVAL);
});