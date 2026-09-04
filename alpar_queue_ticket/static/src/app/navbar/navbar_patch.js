/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { useState, onMounted, onWillUnmount } from "@odoo/owl";

patch(Navbar.prototype, {
    setup() {
        super.setup(...arguments);
        this.queueState = useState({
            waitingCount: 0,
            lastCalled: null,
            loading: false,
        });
        this.orm = this.env.services.orm;

        onMounted(() => {
            this.refreshQueueCount();
            this.queueInterval = setInterval(() => this.refreshQueueCount(), 6000);
        });

        onWillUnmount(() => {
            if (this.queueInterval) {
                clearInterval(this.queueInterval);
            }
        });
    },

    async refreshQueueCount() {
        try {
            const status = await this.orm.call("queue.ticket", "get_queue_status", []);
            if (status) {
                const configQueueType = this.pos.config.queue_type_id;
                const queueTypeId = configQueueType ? (Array.isArray(configQueueType) ? configQueueType[0] : configQueueType) : null;
                if (queueTypeId && status.by_type && status.by_type[queueTypeId]) {
                    this.queueState.waitingCount = status.by_type[queueTypeId].waiting_count || 0;
                } else {
                    this.queueState.waitingCount = status.waiting_caja ?? status.total_waiting ?? 0;
                }
            }
        } catch (e) {
            // Silencioso ante pérdidas temporales de red
        }
    },

    async callNextQueueTicket() {
        if (this.queueState.loading) return;
        this.queueState.loading = true;
        try {
            const station = this.pos.config.name || "Caja";
            const configQueueType = this.pos.config.queue_type_id;
            const queueTypeId = configQueueType ? (Array.isArray(configQueueType) ? configQueueType[0] : configQueueType) : null;

            const ticket = await this.orm.call("queue.ticket", "call_next", [], {
                station: station,
                queue_type_id: queueTypeId,
                queue_type: queueTypeId ? undefined : "caja",
            });

            if (!ticket) {
                this.notification.add("No hay clientes en espera en la fila.", { type: "info" });
                return;
            }

            this.queueState.lastCalled = ticket.number;
            const typeLabel = ticket.queue_type_name ? ` (${ticket.queue_type_name})` : "";
            this.notification.add(`¡Llamando turno ${ticket.number}${typeLabel} a ${station}!`, { type: "success" });

            // Si el cliente estaba registrado en Odoo, asociarlo al pedido actual si está libre
            if (ticket.partner_id && this.pos.getOrder()) {
                const partner = this.pos.models["res.partner"]?.get(ticket.partner_id);
                if (partner) {
                    this.pos.getOrder().set_partner(partner);
                }
            }

            await this.refreshQueueCount();
        } catch (err) {
            console.error("Error al llamar turno:", err);
            this.notification.add("Error al comunicar con el servidor de turnos.", { type: "danger" });
        } finally {
            this.queueState.loading = false;
        }
    },
});
