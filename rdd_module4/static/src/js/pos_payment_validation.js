/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);

        const order = this.pos.getOrder();
        const invalidLine = order.getOrderlines().find((line) => line.getQuantity() === 0);
        if (!invalidLine) {
            return;
        }

        this.env.services.dialog.add(AlertDialog, {
            title: "Cantidad en cero",
            body: "No puedes proceder al pago con líneas con cantidad en cero. Corrige el pedido antes de continuar.",
        });
        setTimeout(() => this.pos.onClickBackButton(), 1000);
    },
});
