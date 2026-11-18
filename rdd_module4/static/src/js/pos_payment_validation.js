/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

console.log("[pos_validate_payment_zero_qty] Patch cargado correctamente en PaymentScreen!");

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        console.log("[pos_validate_payment_zero_qty] setup ejecutado en PaymentScreen");

        const order = this.pos.get_order();
        const invalidLine = order.get_orderlines().find(line => line.get_quantity() === 0);

        if (invalidLine) {
            console.log("[pos_validate_payment_zero_qty] Línea con cantidad cero detectada en PaymentScreen:", invalidLine);

            this.env.services.dialog.add(AlertDialog, {
                title: "Cantidad en cero",
                body: "No puedes proceder al pago con líneas con cantidad en cero. Corrige el pedido antes de continuar.",
            });

            // Regresar tras 3 segundos automáticamente
            setTimeout(() => {
                console.log("[pos_validate_payment_zero_qty] Regresando automáticamente a ProductScreen");
                this.pos.onClickBackButton();
            }, 1000);
        } else {
            console.log("[pos_validate_payment_zero_qty] Ninguna línea con cantidad cero detectada en PaymentScreen");
        }
    },
});


///** @odoo-module **/

//APPTURA LOOG DE 0 O NORMALES
//import { patch } from "@web/core/utils/patch";
//import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
//import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
//
//console.log("[pos_validate_payment_zero_qty] Patch cargado correctamente en PaymentScreen!");
//
//patch(PaymentScreen.prototype, {
//    setup() {
//        super.setup(...arguments);
//        console.log("[pos_validate_payment_zero_qty] setup ejecutado en PaymentScreen");
//
//        const order = this.pos.get_order();
//        const invalidLine = order.get_orderlines().find(line => line.get_quantity() === 0);
//
//        if (invalidLine) {
//            console.log("[pos_validate_payment_zero_qty] Línea con cantidad cero detectada en PaymentScreen:", invalidLine);
//            this.shouldBlockPayment = true;
//        } else {
//            console.log("[pos_validate_payment_zero_qty] Ninguna línea con cantidad cero detectada en PaymentScreen");
//            this.shouldBlockPayment = false;
//        }
//    },
//
//    async mounted() {
//        super.mounted(...arguments);
//
//        if (this.shouldBlockPayment) {
//            console.log("[pos_validate_payment_zero_qty] Mostrando AlertDialog en mounted()");
//            await this.env.services.dialog.add(AlertDialog, {
//                title: "Cantidad en cero",
//                body: "No puedes proceder al pago con líneas con cantidad en cero. Corrige el pedido antes de continuar.",
//            });
//
//            this.pos.setScreen("ProductScreen");
//        }
//    },
//});
