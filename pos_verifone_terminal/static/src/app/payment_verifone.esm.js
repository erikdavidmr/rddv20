/** @odoo-module **/


import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { _t } from "@web/core/l10n/translation";


const verifoneCodeMessages = {
    "-11": "Transacción Cancelada",
    "00": "Aprobada",
    "02": "Llame al emisor",
    "04": "Retener Tarjeta",
    "05": "Denegada",
    "07": "Declinada",
    "08": "Aprobar con identificación",
    "09": "Transacción duplicada",
    "10": "Aprobación parcial",
    "11": "Aprobado VIP",
    "12": "Transacción no permitida",
    "13": "Monto inválido",
    "14": "Número de tarjeta inválido",
    "15": "No se pudo enviar transacción (ruteo)",
    "16": "Aprobado, actualizado Track 3",
    "19": "Reintente por favor",
    "21": "Transacción no encontrada o cancelada",
    "22": "Tarifa o comisión no aceptada",
    "30": "Transacción no permitida",
    "33": "Tarjeta expirada",
    "34": "Sospecha de fraude",
    "35": "Tienda contacte al adquirente",
    "36": "Retener tarjeta",
    "37": "Llame al emisor",
    "38": "Número de intentos de NIP excedido",
    "39": "Tipo de cuenta inválida",
    "40": "Función no soportada",
    "41": "Retener tarjeta",
    "43": "Retener tarjeta",
    "51": "Fondos insuficientes",
    "55": "NIP inválido",
    "56": "Sin registro de tarjeta",
    "57": "Transacción no permitida al tarjetahabiente",
    "58": "Transacción no permitida (Terminal)",
    "60": "Llame a emisor para autorización",
    "61": "Excede monto máximo de retiro",
    "62": "Tarjeta restringida",
    "63": "Violación de seguridad",
    "65": "Excede monto diario de retiro",
    "66": "Llamar al banco adquirente",
    "75": "Máximo número de NIP",
    "85": "Declinada, sin motivo",
    "90": "Corte en proceso",
    "91": "Error en el emisor",
    "92": "No permitido por leyes locales",
    "94": "Transacción duplicada",
    "96": "Error del sistema",
    "99": "Rechazada",
};


export class PaymentVerifoneMiddleware extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.paymentNotificationResolver = null;
    }

    async sendPaymentRequest(pay_line) {
        const order = pay_line?.pos_order_id;

        if (!order || !pay_line) {
            return this._handle_error(_t("No se pudo obtener la orden o línea de pago."));
        }

        let retries = 0;
        while ((!this.pos || !this.pos.config?.current_session_id) && retries < 20) {
            console.warn("[Verifone] Esperando this.pos.config.current_session_id...");
            await new Promise((resolve) => setTimeout(resolve, 100));
            retries++;
        }

        const session_id = this.pos.session?.id;
        const method_id = this.payment_method_id.id;
        const uuid_str = pay_line.uuid;

        if (!session_id || !method_id || !uuid_str) {
            return this._handle_error(_t("Faltan datos para generar el external_reference."));
        }

        const external_reference = `${session_id}_${method_id}_${uuid_str}`;
        const merchant_order_id = `${new Date().toISOString()}--${session_id}--${uuid_str}`;

        const payload = {
            amount: pay_line.amount,
            reference: order.name,
            pos_id: this.pos.config.name,
            LocalPaymentID: order.name,
            InvoiceID: order.name,
            Lane: this.pos.config.name,
            Venue: this.pos.config.name,
            paymentline_uuid: uuid_str,
            merchant_order_id: merchant_order_id,
            external_reference: external_reference,
        };

        pay_line.setPaymentStatus("waitingCard");

        try {
            const response = await fetch("/verifone/proxy", {
                method: "POST",
                body: JSON.stringify(payload),
                headers: { "Content-Type": "application/json" },
            });

            if (!response.ok) {
                throw new Error("Middleware responded with status " + response.status);
            }

            const result = await response.json();
            console.log("[Verifone] Middleware respondió:", result);

            if (result.status === "received") {
                return await new Promise((resolve) => {
                    console.log("[Verifone] Esperando confirmación de terminal...");
                    this.paymentNotificationResolver = resolve;
                });
            } else {
                return this._handle_error(result.message || _t("No se pudo iniciar el pago."));
            }
        } catch (error) {
            return this._handle_error(error.message || _t("Error de conexión con la terminal."));
        }
    }

    async handleVerifoneStatusResponse(payload = {}) {
        console.log("[Verifone] Entrando a handleVerifoneStatusResponse:", payload);

        const line = this.pos.getPendingPaymentLine("verifone_middleware");
        if (!line) {
            console.warn("[Verifone] No se encontró línea de pago pendiente.");
            return;
        }

        const expectedUuid = line.uuid;
        const receivedUuid = payload.paymentline_uuid;

        if (expectedUuid !== receivedUuid) {
            console.warn(`[Verifone] UUID no coincide. Esperado: ${expectedUuid}, Recibido: ${receivedUuid}`);
            this.paymentNotificationResolver?.(false);
            return;
        }

        const raw_code = (payload.code || payload.status || "").toString().trim();
        const cleaned_code = raw_code.replace(/\s+/g, "");
        let code;

        // si empieza con "-", respétalo exactamente (ej. "-11")
        if (cleaned_code.startsWith("-")) {
            code = cleaned_code;
        } else {
            code = cleaned_code.padStart(2, "0");
        }

        console.log("[Verifone] Código final:", code);

        const message = verifoneCodeMessages[code] || `Código desconocido: ${code}`;

        if (payload.status === "approved" || code === "00") {
            line.setPaymentStatus("done");
            line.transaction_id = payload.auth_code || payload.transaction_id;
            line.card_type = payload.card_type || "Verifone";

            this.env.services.notification.add(_t("✅ Pago aprobado: ") + message, {
                type: "success",
            });

            this.paymentNotificationResolver?.(true);
        } else {
            line.setPaymentStatus("retry");
            this._show_error(message || "❌ Pago rechazado.");
            this.paymentNotificationResolver?.(false);
        }
    }



    _handle_error(msg) {
        this._show_error(msg);
        return false;
    }

    _show_error(msg, title) {
        this.env.services.dialog.add(AlertDialog, {
            title: title || _t("Error con la terminal"),
            body: msg,
        });
    }
}
