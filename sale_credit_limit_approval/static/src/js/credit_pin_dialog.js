/** @odoo-module **/
// sale_credit_limit_approval/static/src/js/credit_pin_dialog.js

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class CreditPinDialog extends Component {
    static template = "sale_credit_limit_approval.CreditPinDialog";
    static components = { Dialog };

    static props = {
        title: { type: String, default: "Aprobación por PIN" },
        orderId: { type: Number },
        onSuccess: { type: Function },
        close: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            pin: "",
            loading: false,
            errorMessage: null,
        });
        this.inputRef = useRef("pinInput");

        // Auto-focus the PIN input when the dialog opens
        onMounted(() => {
            const input = document.getElementById("credit_approval_pin");
            if (input) {
                input.focus();
            }
        });
    }

    onKeydown(ev) {
        // Allow Enter to submit
        if (ev.key === "Enter" && this.state.pin && !this.state.loading) {
            this.onConfirm();
        }
    }

    async onConfirm() {
        this.state.errorMessage = null;
        this.state.loading = true;

        try {
            await this.orm.call(
                "sale.order",
                "action_approve_credit_by_pin",
                [[this.props.orderId], this.state.pin],
            );
            // Success — let the parent reload the record
            this.props.close();
            this.props.onSuccess();
        } catch (error) {
            // Show the server error inline without closing the dialog.
            // In Odoo 18, UserError messages are in error.data.arguments[0].
            const serverMessage =
                error?.data?.arguments?.[0] ||
                error?.data?.message ||
                error?.message ||
                "Error al verificar el PIN. Intente nuevamente.";
            this.state.errorMessage = serverMessage;
        } finally {
            this.state.loading = false;
            // Clear the PIN field after each attempt (security best practice)
            this.state.pin = "";
        }
    }

    onCancel() {
        this.props.close();
    }
}
