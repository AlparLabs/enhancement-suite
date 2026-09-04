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
                this.queueState.waitingCount = status.waiting_caja || 0;
            }
        } catch (e) {
            // Silencioso ante p?rdidas temporales de red
        }
    },

    async callNextQueueTicket() {
        if (this.queueState.loading) return;
        this.queueState.loading = true;
        try {
            const station = this.pos.config.name || "Caja";
            const ticket = await this.orm.call("queue.ticket", "call_next", ["caja", station]);
            if (!ticket) {
                this.notification.add("No hay clientes en espera en la fila de Caja.", { type: "info" });
                return;
            }

            this.queueState.lastCalled = ticket.number;
            this.notification.add(`?Llamando turno ${ticket.number} a ${station}!`, { type: "success" });

            // Si el cliente estaba registrado en Odoo, asociarlo al pedido actual si est? libre
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
