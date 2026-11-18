/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { qrCodeSrc } from "@point_of_sale/utils";

console.log("[pos_disable_qr_patch] Patch cargado correctamente en PosOrder!");

patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        const originalData = super.export_for_printing(baseUrl, headerData);

        console.log("[pos_disable_qr_patch] Exportando ticket - not_print_qr_url:", this.config.not_print_qr_url);

        return {
            ...originalData,
            pos_qr_code:
                this.company.point_of_sale_use_ticket_qr_code &&
                !this.config.not_print_qr_url &&  // tu condición extra
                this.finalized &&
                qrCodeSrc(`${baseUrl}/pos/ticket/`),
        };
    },
});
