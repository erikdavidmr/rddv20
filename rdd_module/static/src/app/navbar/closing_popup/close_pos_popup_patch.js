/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { ConfirmationDialog, AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { useState, useRef, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog"; // Make sure this import is correct
import { useService } from "@web/core/utils/hooks";
import { xml } from "@odoo/owl";

const { Component } = owl;


// Define ManagerPinPopup FIRST, as it's used inside ManagerPinDialog's template
class ManagerPinPopup extends Component {
    static template = "rdd_module.ManagerPinPopup"; // Assuming this is still the external XML template
    setup() {
        console.log("ManagerPinPopup: setup START");
        super.setup();
        this.state = useState({ pin: '' });
        this.inputRef = useRef('pinInput');
        onMounted(() => {
            console.log("ManagerPinPopup: onMounted");
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
        });
        console.log("ManagerPinPopup: setup END");
    }

    confirm() {
        console.log("ManagerPinPopup: confirm");
        this.props.close({ confirmed: true, pin: this.state.pin });
    }

    cancel() {
        console.log("ManagerPinPopup: cancel");
        this.props.close({ confirmed: false });
    }
    // render() is not strictly needed
}


// Define ManagerPinDialog, which uses <Dialog> and <ManagerPinPopup> in its template
class ManagerPinDialog extends Dialog {

    // *** ADD Dialog BACK to static components HERE ***
    // This tells the template compiler that <Dialog> is a component used within this template.
    static components = { Dialog, ManagerPinPopup };

    // Define the template for this custom dialog
    // Template uses <Dialog> and <ManagerPinPopup> tags
    // Keep the simplified template without size/className props on the <Dialog> tag
    static template = xml`
        <Dialog>
            <h2 class="modal-title"><t t-esc="props.title"/></h2>
            <ManagerPinPopup close="props.close"/>
        </Dialog>
    `;

    // Define props expected by this component (ManagerPinDialog).
    // These props come from dialogService.add call and the service injecting 'close'.
    static props = {
        title: { type: String, optional: true },
        close: { type: Function },
        size: { type: String, optional: true },
        className: { type: String, optional: true },
        "*": true,
    };

    // setup method is inherited from Dialog unless overridden
    // setup() {
    //    super.setup();
    //    // Add custom setup logic here if needed
    // }
}

// Now patch ClosePosPopup
patch(ClosePosPopup.prototype, {
    setup() {
        console.log("ClosePosPopup: setup");
        super.setup();
        this.dialogService = useService('dialog');
        this.dialog = useService("dialog");
        this.isClosing = false;
    },

    async confirm() {
        console.log("ClosePosPopup: confirm (Patched)");
        if (this.isClosing) {
             console.log("ClosePosPopup: Already closing, returning.");
            return;
        }
        this.isClosing = true;
         console.log("ClosePosPopup: isClosing set to true.");

        try {
            console.log("ClosePosPopup: Calling showManagerPinPopup...");
            const result = await this.showManagerPinPopup();
            console.log("ClosePosPopup: showManagerPinPopup returned:", result);

            if (result && result.confirmed) {
                const { pin } = result;
                console.log("ClosePosPopup: PIN entered:", pin);
                if (!this.isValidManagerPin(pin)) {
                    console.log("ClosePosPopup: Invalid PIN.");
                    this.showError(_t("Invalid PIN. Authorization is required to close the session."));
                    return;
                }
                console.log("ClosePosPopup: PIN is valid. Proceeding with closing logic.");
            } else {
                console.log("ClosePosPopup: Manager PIN dialog was cancelled.");
                return;
            }

        } catch (error) {
            console.error("ClosePosPopup: confirm (Error):", error);
            this.showError(_t("An unexpected error occurred during the closing process. Please contact support."));
            return;
        } finally {
             console.log("ClosePosPopup: confirm finally block reached. Resetting isClosing to false.");
             this.isClosing = false;
        }

        console.log("ClosePosPopup: Checking cash control and difference.");
        if (!this.pos.config.cash_control || this.env.utils.floatIsZero(this.getMaxDifference())) {
            console.log("ClosePosPopup: No cash control or zero difference. Closing session.");
            await this.closeSession();
            return;
        }
        console.log("ClosePosPopup: Cash control active with difference.");
        if (this.hasUserAuthority()) {
            console.log("ClosePosPopup: User has authority for difference.");
            const response = await this.dialog.add(ConfirmationDialog, {
                title: _t("Payments Difference"),
                body: _t("The money counted doesn't match what we expected. Want to log the difference for the books?"),
                confirmLabel: _t("Proceed Anyway"),
                cancelLabel: _t("Discard"),
            });
            if (response) {
                 console.log("ClosePosPopup: User confirmed difference. Closing session.");
                await this.closeSession();
                return;
            }
            console.log("ClosePosPopup: User discarded difference.");
            return;
        } else {
            console.log("ClosePosPopup: User does not have authority for difference.");
            this.dialog.add(AlertDialog, {
                title: _t("Payments Difference"),
                body: _t(
                    "The maximum difference allowed is %s.\nPlease contact your manager to accept the closing difference.",
                    this.env.utils.formatCurrency(this.props.amount_authorized_diff)
                ),
            });
            return;
        }
    },

    showManagerPinPopup() {
        console.log("ClosePosPopup: showManagerPinPopup called.");
        return new Promise((resolve) => {
            console.log("ClosePosPopup: Creating ManagerPinDialog via dialogService.add");
            // Pass props needed by ManagerPinDialog (like the title, size, className)
            // ManagerPinDialog accepts these props.
            const dialog = this.dialogService.add(ManagerPinDialog, {
                 title: _t("Manager Authorization Required"),
                 size: 'md', // Pass size as a prop here
                 className: 'o_pos_manager_pin_dialog', // Pass className as a prop here
                 // The service will add the 'close' prop automatically
                 // Our ManagerPinDialog is defined to accept these props.
            }, {
                onClose: (resultOfClose) => {
                    console.log("ClosePosPopup: Dialog service onClose called with result:", resultOfClose);
                    resolve(resultOfClose);
                }
            });
             console.log("ClosePosPopup: dialogService.add called for ManagerPinDialog.");
        });
    },

    isValidManagerPin(pin) {
        console.log("ClosePosPopup: isValidManagerPin called with PIN:", pin);
        const managers = this.pos.config.advance_employee_ids || [];
        console.log("ClosePosPopup: Authorized managers from config:", managers);
        const isValid = managers.some(manager => manager.pin && manager.pin.toString() === pin.toString());
        console.log("ClosePosPopup: PIN validity check result:", isValid);
        return isValid;
    },

    showError(message) {
        console.log("ClosePosPopup: showError called:", message);
        this.dialog.add(AlertDialog, {
            title: _t("Authorization Error"),
            body: message,
        });
    },
});