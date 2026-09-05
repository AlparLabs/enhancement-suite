// Pantalla TV de Turnos Dinámica - AlparLabs
(function () {
    let lastKnownTicketId = null;
    let audioCtx = null;
    let currentCompanyId = null;

    // Inicializar Web Audio API para Ding-Dong sintetizado
    function initAudio() {
        if (!audioCtx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                audioCtx = new AudioContext();
            }
        }
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }

    // Sonido sintetizado Ding-Dong de dos tonos (aeropuerto/banco)
    function playChime() {
        try {
            initAudio();
            if (!audioCtx) return;

            const now = audioCtx.currentTime;

            // Tono 1: Mi5 (659 Hz)
            const osc1 = audioCtx.createOscillator();
            const gain1 = audioCtx.createGain();
            osc1.type = 'sine';
            osc1.frequency.setValueAtTime(659.25, now);
            gain1.gain.setValueAtTime(0, now);
            gain1.gain.linearRampToValueAtTime(0.3, now + 0.05);
            gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
            osc1.connect(gain1);
            gain1.connect(audioCtx.destination);
            osc1.start(now);
            osc1.stop(now + 0.65);

            // Tono 2: Do5 (523 Hz) con retraso de 0.35s
            const osc2 = audioCtx.createOscillator();
            const gain2 = audioCtx.createGain();
            osc2.type = 'sine';
            osc2.frequency.setValueAtTime(523.25, now + 0.35);
            gain2.gain.setValueAtTime(0, now + 0.35);
            gain2.gain.linearRampToValueAtTime(0.35, now + 0.4);
            gain2.gain.exponentialRampToValueAtTime(0.001, now + 1.2);
            osc2.connect(gain2);
            gain2.connect(audioCtx.destination);
            osc2.start(now + 0.35);
            osc2.stop(now + 1.25);
        } catch (e) {
            console.warn("No se pudo reproducir audio chime:", e);
        }
    }

    // Actualizar reloj digital
    function updateClock() {
        const now = new Date();
        const timeEl = document.getElementById('display-clock');
        const dateEl = document.getElementById('display-date');
        if (timeEl) {
            timeEl.textContent = now.toLocaleTimeString('es-AR', { hour12: false });
        }
        if (dateEl) {
            dateEl.textContent = now.toLocaleDateString('es-AR', {
                weekday: 'long',
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Renderizar datos en pantalla
    function renderDisplay(data) {
        if (!data) return;

        // Actualizar último llamado (Hero)
        const heroNumber = document.getElementById('hero-number');
        const heroStation = document.getElementById('hero-station');
        const heroCustomer = document.getElementById('hero-customer');
        const heroSector = document.getElementById('hero-sector');
        const heroCard = document.querySelector('.hero-call-card');

        if (data.last_called) {
            if (heroNumber) heroNumber.textContent = data.last_called.number || '---';
            if (heroStation) heroStation.textContent = data.last_called.station || '---';
            if (heroCustomer) heroCustomer.textContent = data.last_called.customer_name || '';

            const queueColor = data.last_called.queue_color || '#2563eb';
            const sectorName = data.last_called.queue_type_name || 'General';
            if (heroSector) {
                heroSector.textContent = 'Sector: ' + sectorName;
                heroSector.style.backgroundColor = queueColor + '18';
                heroSector.style.color = queueColor;
                heroSector.style.borderColor = queueColor + '33';
            }

            // Si es un ticket nuevo, hacer sonar el Ding-Dong y activar animación
            if (lastKnownTicketId !== null && data.last_called.id !== lastKnownTicketId) {
                playChime();
                if (heroCard) {
                    heroCard.classList.add('flash-call');
                    setTimeout(() => heroCard.classList.remove('flash-call'), 6000);
                }
            }
            lastKnownTicketId = data.last_called.id;
        } else {
            if (heroNumber) heroNumber.textContent = '---';
            if (heroStation) heroStation.textContent = '---';
            if (heroCustomer) heroCustomer.textContent = '';
            if (heroSector) {
                heroSector.textContent = 'Sector: General';
                heroSector.style.backgroundColor = '#2563eb18';
                heroSector.style.color = '#2563eb';
                heroSector.style.borderColor = '#2563eb33';
            }
        }

        // Actualizar Resumen de Espera
        const totalBadge = document.getElementById('total-waiting-badge');
        if (totalBadge) {
            totalBadge.textContent = 'Total en espera: ' + (data.total_waiting || 0);
        }

        const summaryGrid = document.getElementById('summary-grid');
        if (summaryGrid && data.waiting_summary) {
            summaryGrid.innerHTML = data.waiting_summary.map(ws => {
                const color = ws.color || '#2563eb';
                return `
                    <div class="summary-item">
                        <div class="summary-item-name" style="color: ${color};">${escapeHtml(ws.name)}</div>
                        <div class="summary-item-count" style="color: ${color};">${ws.waiting_count || 0}</div>
                    </div>
                `;
            }).join('');
        }

        // Actualizar Lista Unificada de Últimos Llamados
        const recentList = document.getElementById('recent-calls-list');
        if (recentList) {
            if (data.recent_called && data.recent_called.length > 0) {
                recentList.innerHTML = data.recent_called.map(rc => {
                    const color = rc.queue_color || '#0f172a';
                    const sectorColor = rc.queue_color || '#2563eb';
                    const sectorName = rc.queue_type_name || 'General';
                    return `
                        <div class="called-row-item">
                            <div class="col-ticket-num" style="color: ${color};">${escapeHtml(rc.number)}</div>
                            <div class="col-station-info">${escapeHtml(rc.station)}</div>
                            <div>
                                <span class="col-sector-badge" style="background-color: ${sectorColor}18; color: ${sectorColor}; border: 1px solid ${sectorColor}33;">
                                    ${escapeHtml(sectorName)}
                                </span>
                            </div>
                            <div class="col-call-time">${escapeHtml(rc.call_time || '')}</div>
                        </div>
                    `;
                }).join('');
            } else {
                recentList.innerHTML = '<div class="empty-calls-state"><span>No hay llamados registrados hoy</span></div>';
            }
        }

        // Actualizar Turnos en Cola (Próximos en espera)
        const waitingContainer = document.getElementById('waiting-tickets-container');
        if (waitingContainer) {
            if (data.waiting_tickets && data.waiting_tickets.length > 0) {
                waitingContainer.innerHTML = data.waiting_tickets.map(wt => {
                    const color = wt.queue_color || '#2563eb';
                    const sectorName = wt.queue_type_name || '';
                    return `
                        <div class="waiting-ticket-pill">
                            <span class="waiting-pill-num" style="color: ${color};">${escapeHtml(wt.number)}</span>
                            <span class="waiting-pill-sector" style="background-color: ${color}18; color: ${color};">${escapeHtml(sectorName)}</span>
                        </div>
                    `;
                }).join('');
            } else {
                waitingContainer.innerHTML = '<span class="empty-waiting-notice">No hay turnos pendientes en espera en este momento</span>';
            }
        }
    }

    // Polling de respaldo
    async function fetchDisplayData() {
        try {
            const resp = await fetch('/turnos/api/display_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {
                        company_id: currentCompanyId
                    }
                })
            });
            const result = await resp.json();
            if (result && result.result) {
                renderDisplay(result.result);
                updateConnectionStatus(true);
            }
        } catch (err) {
            console.warn("Error en polling de turnos:", err);
            updateConnectionStatus(false);
        }
    }

    function updateConnectionStatus(online) {
        const dot = document.querySelector('.status-dot');
        const txt = document.getElementById('status-text');
        if (dot && txt) {
            if (online) {
                dot.className = 'status-dot online';
                txt.textContent = 'Conectado en tiempo real';
            } else {
                dot.className = 'status-dot offline';
                txt.textContent = 'Reconectando con el servidor...';
            }
        }
    }

    // Inicio al cargar página
    document.addEventListener('DOMContentLoaded', () => {
        // Habilitar audio con cualquier interacción del usuario (requerido por navegadores)
        window.addEventListener('click', initAudio, { once: true });
        window.addEventListener('keydown', initAudio, { once: true });

        // Cargar datos iniciales inyectados en HTML
        const initialEl = document.getElementById('initial-data');
        if (initialEl) {
            if (initialEl.dataset.companyId) {
                currentCompanyId = parseInt(initialEl.dataset.companyId) || null;
            } else {
                const urlParams = new URLSearchParams(window.location.search);
                const qCompany = urlParams.get('company_id');
                if (qCompany) {
                    currentCompanyId = parseInt(qCompany) || null;
                }
            }

            if (initialEl.dataset.json) {
                try {
                    const initialData = JSON.parse(initialEl.dataset.json);
                    renderDisplay(initialData);
                    if (initialData.last_called) {
                        lastKnownTicketId = initialData.last_called.id;
                    }
                } catch (e) {
                    console.error("Error parseando datos iniciales:", e);
                }
            }
        }

        // Iniciar reloj
        updateClock();
        setInterval(updateClock, 1000);

        // Polling cada 3 segundos
        setInterval(fetchDisplayData, 3000);
    });
})();
