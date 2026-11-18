/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(ClosePosPopup.prototype, {
    async confirm() {
        if (!this.pos.config.cash_control || this.env.utils.floatIsZero(this.getMaxDifference())) {
            await this.closeSession();
            return;
        }
        
        if (this.hasUserAuthority()) {
            const response = await ask(this.dialog, {
                title: _t("Payments Difference"),
                body: _t(
                    "The money counted doesn't match what we expected. Want to log the difference for the books?"
                ),
                confirmLabel: _t("Proceed Anyway"),
                // Removido cancelLabel: _t("Discard"),
            }, {
                // Opciones para deshabilitar el botón de cerrar (X)
                backdrop: false,
                technical: false
            });
            
            if (response) {
                return this.closeSession();
            }
            return;
        }
        
        this.dialog.add(ConfirmationDialog, {
            title: _t("Payments Difference"),
            body: _t(
                "The maximum difference allowed is %s.\nPlease contact your manager to accept the closing difference.",
                this.env.utils.formatCurrency(this.props.amount_authorized_diff)
            ),
        }, {
            // Opciones para deshabilitar el botón de cerrar (X)
            backdrop: false,
            technical: false
        });
    }
});