// Pantalla TV de Turnos Dinámica - AlparLabs
(function () {
    let lastKnownTicketId = null;
    let audioCtx = null;

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

    // Renderizar datos en pantalla
    function renderDisplay(data) {
        if (!data) return;

        // Actualizar último llamado
        const heroNumber = document.getElementById('hero-number');
        const heroStation = document.getElementById('hero-station');
        const heroCustomer = document.getElementById('hero-customer');
        const heroSection = document.querySelector('.hero-call-section');

        if (data.last_called) {
            heroNumber.textContent = data.last_called.number || '---';
            heroStation.textContent = data.last_called.station || '---';
            heroCustomer.textContent = data.last_called.customer_name || '';

            // Si es un ticket nuevo, hacer sonar el Ding-Dong y parpadear
            if (lastKnownTicketId !== null && data.last_called.id !== lastKnownTicketId) {
                playChime();
                if (heroSection) {
                    heroSection.classList.add('flash-call');
                    setTimeout(() => heroSection.classList.remove('flash-call'), 7000);
                }
            }
            lastKnownTicketId = data.last_called.id;
        }

        // Renderizar grilla de categorías dinámicas
        const container = document.getElementById('categories-container');
        if (container && data.categories && data.categories.length > 0) {
            let colClass = "col-md-6";
            if (data.categories.length === 1) colClass = "col-12";
            else if (data.categories.length === 3) colClass = "col-md-4";
            else if (data.categories.length === 4) colClass = "col-md-6 col-lg-3";
            else if (data.categories.length > 4) colClass = "col-md-4";

            container.innerHTML = data.categories.map(cat => {
                const color = cat.color || "#38bdf8";
                const iconHtml = cat.icon ? `<i class="fa ${cat.icon} me-2"></i>` : '';
                const ticketsHtml = (cat.called_tickets && cat.called_tickets.length > 0)
                    ? cat.called_tickets.map(t => `
                        <div class="ticket-item">
                            <span class="ticket-badge-number" style="color: ${color};">${t.number}</span>
                            <div class="text-end">
                                <div class="ticket-station-name text-white">${t.station}</div>
                                <small class="text-secondary">${t.customer_name || ''}</small>
                            </div>
                        </div>
                    `).join('')
                    : '<div class="empty-state text-center text-secondary py-4">No hay llamados activos</div>';

                return `
                    <div class="${colClass}">
                        <div class="card h-100 queue-column-card border-0 rounded-4 shadow-lg p-3" style="border-top: 4px solid ${color} !important;">
                            <div class="column-header d-flex justify-content-between align-items-center border-bottom border-dark-subtle pb-2 mb-3">
                                <h2 class="fs-3 fw-bold mb-0" style="color: ${color};">
                                    ${iconHtml}${cat.name.toUpperCase()}
                                </h2>
                                <span class="badge bg-secondary fs-6">Espera: ${cat.waiting_count || 0}</span>
                            </div>
                            <div class="called-list d-flex flex-column gap-2">
                                ${ticketsHtml}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
    }

    // Polling de respaldo
    async function fetchDisplayData() {
        try {
            const resp = await fetch('/turnos/api/display_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: "2.0", params: {} })
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
        if (initialEl && initialEl.dataset.json) {
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

        // Iniciar reloj
        updateClock();
        setInterval(updateClock, 1000);

        // Polling cada 3 segundos
        setInterval(fetchDisplayData, 3000);
    });
})();
