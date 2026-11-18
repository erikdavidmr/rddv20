/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { registry } from "@web/core/registry";

// WebSocket listener al estilo Mercado Pago
patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);

        this.data.connectWebSocket("VERIFONE_LATEST_RESPONSE", (payload) => {
            console.log("[Verifone] Evento VERIFONE_LATEST_RESPONSE recibido vía WebSocket:", payload);

            const line = this.getPendingPaymentLine("verifone_middleware");
            if (!line) {
                console.warn("[Verifone] Línea pendiente no encontrada.");
                return;
            }

            if (line.uuid !== payload.paymentline_uuid) {
                console.warn(`[Verifone] UUID no coincide. Esperado: ${line.uuid}, recibido: ${payload.paymentline_uuid}`);
                return;
            }

            const terminal = line.payment_method_id?.payment_terminal;
            if (!terminal?.handleVerifoneStatusResponse) {
                console.warn("[Verifone] Método no válido o sin handler");
                return;
            }

            // ✅ Ejecutar respuesta
            terminal.handleVerifoneStatusResponse(payload);

            // ✅ Mostrar notificación visual
            if (payload.status === "approved") {
                this.env.services.notification.add("✅ Pago recibido desde Verifone", {
                    type: "success",
                });
            } else if (payload.status === "declined") {
                this.env.services.notification.add("❌ Pago rechazado por Verifone", {
                    type: "warning",
                });
            }

        });

        console.log("[Verifone] WebSocket activo para VERIFONE_LATEST_RESPONSE");
    },
});

// Exponer POS globalmente para pruebas desde consola
registry.category("pos_payment_method").add("verifone_expose_pos", {
    async setup(pos) {
        await pos.ready;
        window.pos = pos;
        console.log("[Verifone] POS expuesto globalmente como 'window.pos'");
    },
});
