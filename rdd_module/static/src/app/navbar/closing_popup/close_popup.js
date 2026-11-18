/** @odoo-module **/

import { AbstractPopup } from "@point_of_sale/app/utils/popup_service/popup";
import { useState } from "@odoo/owl";

export class ManagerPinPopup extends AbstractPopup {
    setup() {
        super.setup();
        this.state = useState({ pin: '' });
    }

    confirm() {
        this.props.resolve({ confirmed: true, pin: this.state.pin });
        this.env.services.popup.remove(this);
    }

    cancel() {
        this.props.resolve({ confirmed: false });
        this.env.services.popup.remove(this);
    }
}

ManagerPinPopup.template = "rdd_module.ManagerPinPopup";