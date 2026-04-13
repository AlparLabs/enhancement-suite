/** @odoo-module **/
// sale_credit_limit_approval/static/src/js/approve_pin_button.js
//
// Patches the sale.order form view so that clicking the "Aprobar con PIN"
// button opens the CreditPinDialog instead of making a normal RPC call.

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { CreditPinDialog } from "./credit_pin_dialog";

patch(FormController.prototype, {
    setup() {
        super.setup();
        // Only attach the dialog service if we are on a sale.order form
        this._dialogService = useService("dialog");
        this._actionService = useService("action");
    },

    /**
     * Intercept the "action_open_pin_dialog" button click.
     * All other button clicks go through the normal Odoo flow.
     */
    async _onButtonClicked(clickParams) {
        if (
            clickParams.name === "action_open_pin_dialog" &&
            this.model.root.resModel === "sale.order"
        ) {
            const orderId = this.model.root.resId;
            this._dialogService.add(CreditPinDialog, {
                title: "Aprobación por PIN de Crédito",
                orderId,
                onSuccess: async () => {
                    // Reload the record so the view reflects the new state
                    await this.model.root.load();
                    this.model.notify();
                },
            });
            // Do NOT call super — we've handled this button ourselves
            return;
        }
        return super._onButtonClicked(clickParams);
    },
});
