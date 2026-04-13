/** @odoo-module **/
// sale_credit_limit_approval/static/src/js/approve_pin_button.js
//
// Patches FormController.onClickViewButton so that clicking "Aprobar con PIN"
// opens the CreditPinDialog instead of making a normal RPC call to the stub.
//
// NOTE: _onButtonClicked does NOT exist in Odoo 18. The correct intercept
// point is onClickViewButton, as confirmed by the browser call stack:
//   onClick (ViewButton) → onClickViewButton (FormController) → doActionButton

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { CreditPinDialog } from "./credit_pin_dialog";

patch(FormController.prototype, {
    setup() {
        super.setup();
        // Must be called during setup so OWL can track the service hook
        this._pinDialogService = useService("dialog");
    },

    onClickViewButton({ clickParams, record }) {
        if (
            clickParams?.name === "action_open_pin_dialog" &&
            this.model.root.resModel === "sale.order"
        ) {
            const rec = record || this.model.root;
            const model = this.model;

            this._pinDialogService.add(CreditPinDialog, {
                title: "Aprobación por PIN de Crédito",
                orderId: rec.resId,
                onSuccess: async () => {
                    // Reload record so the view reflects the new confirmed state
                    await model.root.load();
                    model.notify();
                },
            });
            // Return without calling super — we've handled this button ourselves
            return;
        }
        return super.onClickViewButton({ clickParams, record });
    },
});
