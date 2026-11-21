/*@odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { DenyPopup } from "../screens/popUps/deny_popUp";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

console.log("[Security] Módulo de restricciones de líneas con soporte OTP cargado");

patch(OrderSummary.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },

    async confirm(selected_manager) {
        const manager = selected_manager ? selected_manager.id : false;
        const cashier1 = this.pos.accessRight.cashier?.id;
        const session_id = this.pos.session.id;
        const state = 'orderline_deleted';
        const order = this.pos.getOrder();
        const receipt = order.uuid;
        const order_num = order.tracking_number;

        await this.orm.call("manager.approval", "getting_all_data", [{
            session_id,
            manager,
            cashier1,
            state,
            receipt,
            order_num
        }]);
    },

    async updateSelectedOrderline({ buffer, key }) {
        const order = this.pos.getOrder();
        const selectedLine = order.getSelectedOrderline();

        if (key === 'Backspace') {
            if (!selectedLine) {
                return super.updateSelectedOrderline(...arguments);
            }

            const product = selectedLine.getProduct ? selectedLine.getProduct() : selectedLine.product_id;
            if (!product) {
                return super.updateSelectedOrderline(...arguments);
            }

            // Verificar si necesita aprobación del manager
            const needsApproval = this._checkIfNeedsManagerApproval(order, product.id);

            if (needsApproval) {
                const approved = await this._requestManagerApproval(product, selectedLine, order);
                if (!approved) {
                    return;
                }
            }

            // Si está aprobado o no requiere autorización, eliminar línea
            order.removeOrderline(selectedLine);
            return;
        }

        return super.updateSelectedOrderline(...arguments);
    },

    _checkIfNeedsManagerApproval(order, productId) {
        if (!this.pos.config.enable_pos_restaurant_restiction || !this.pos.config.enable_restriction_on_orderline_delete) {
            return false;
        }

        // Si el usuario logueado en caja es manager, no necesita pedir aprobación
        if (this.pos.accessRight.cashier?._role === 'manager') {
            return false;
        }

        const orderlines = order.getOrderlines();
        if (!orderlines.length) {
            return false;
        }

        return orderlines.some(line => {
            const lineProduct = line.getProduct ? line.getProduct() : line.product_id;
            return lineProduct && lineProduct.id === productId;
        });
    },

    async _requestManagerApproval(product, selectedLine, order) {
        const productName = product.display_name || product.name || _t("Producto");
        const qty = selectedLine ? (selectedLine.getQuantity ? selectedLine.getQuantity() : selectedLine.qty) : 1;
        const price = selectedLine ? (selectedLine.price_subtotal_incl || (selectedLine.prices?.total_included) || selectedLine.price_unit || 0) : 0;

        // 1. Mostrar diálogo de autorización híbrido (PIN o OTP Remoto)
        const actionChoice = await makeAwaitable(this.dialog, DenyPopup, {
            title: _t("Autorización Requerida"),
            body: _t("Para eliminar \"%s\" (%s uds - $%s) se requiere autorización de gerencia.", productName, qty, price),
            confirmText: _t("Ingresar PIN"),
            requestOtpText: _t("Solicitar Código Remoto"),
            showRequestOtp: true,
        });

        if (!actionChoice) {
            return false;
        }

        // 2. Opción A: Solicitar Código Temporal (OTP) al Gerente por Correo
        if (actionChoice === 'request_otp') {
            const details = _t("Borrado de línea: %s (%s uds - $%s)", productName, qty, price);
            
            let otpRes;
            try {
                otpRes = await this.orm.call("pos.approval.otp", "action_request_otp", [{
                    config_id: this.pos.config.id,
                    session_id: this.pos.session.id,
                    cashier_id: this.pos.accessRight.cashier?.id,
                    action_type: 'orderline_deleted',
                    details: details,
                    receipt_number: order.uuid,
                    order_number: order.tracking_number,
                }]);
            } catch (err) {
                await this.env.services.dialog.add(AlertDialog, {
                    title: _t("Error de Comunicación"),
                    body: _t("No se pudo enviar la solicitud: ") + (err.message || err),
                });
                return false;
            }

            if (!otpRes || !otpRes.success) {
                await this.env.services.dialog.add(AlertDialog, {
                    title: _t("Error al Solicitar Código"),
                    body: otpRes?.message || _t("No fue posible generar el código temporal."),
                });
                return false;
            }

            // Confirmación de envío
            await this.env.services.dialog.add(AlertDialog, {
                title: _t("Código Temporal Enviado"),
                body: _t("Se ha enviado un código de autorización al correo: %s.\nVigencia: %s minutos. Solicite el código al gerente e ingréselo a continuación.", otpRes.email, otpRes.validity_minutes),
            });

            // Pedir el código recibido
            const enteredOtp = await makeAwaitable(this.dialog, NumberPopup, {
                formatDisplayedValue: (x) => x,
                title: _t("Ingrese Código Temporal OTP (6 dígitos)"),
                startingValue: '',
            });

            if (!enteredOtp) {
                return false;
            }

            // Validar el OTP en backend
            const validation = await this.orm.call("pos.approval.otp", "validate_approval", [
                this.pos.config.id,
                this.pos.session.id,
                enteredOtp,
                'orderline_deleted',
                details,
                this.pos.accessRight.cashier?.id,
                order.uuid,
                order.tracking_number,
            ]);

            if (validation && validation.approved) {
                return true;
            }

            await this.env.services.dialog.add(AlertDialog, {
                title: _t("Código Inválido"),
                body: validation?.message || _t("El código ingresado no es válido o ya expiró."),
            });
            return false;
        }

        // 3. Opción B: Ingresar PIN Fijo de Gerente (Presencial)
        if (actionChoice === 'enter_pin') {
            const enteredPin = await makeAwaitable(this.dialog, NumberPopup, {
                formatDisplayedValue: (x) => x.replace(/./g, "•"),
                title: _t("Ingrese PIN del Gerente o Código"),
                startingValue: '',
            });

            if (!enteredPin) {
                return false;
            }

            // Primero buscar entre gerentes cargados en la sesión POS
            if (this.pos.models["hr.employee"]) {
                const employeesList = this.pos.models["hr.employee"].getAll().filter(
                    (employee) => employee._role === "manager"
                );
                const matchedManager = employeesList.find(emp => emp._pin && emp._pin === Sha1.hash(enteredPin));
                if (matchedManager) {
                    await this.confirm(matchedManager);
                    return true;
                }
            }

            // Si no coincide con un PIN local, validar en backend (por si es un OTP previamente generado)
            const details = _t("Borrado de línea: %s (%s uds - $%s)", productName, qty, price);
            const validation = await this.orm.call("pos.approval.otp", "validate_approval", [
                this.pos.config.id,
                this.pos.session.id,
                enteredPin,
                'orderline_deleted',
                details,
                this.pos.accessRight.cashier?.id,
                order.uuid,
                order.tracking_number,
            ]);

            if (validation && validation.approved) {
                return true;
            }

            await this.env.services.dialog.add(AlertDialog, {
                title: _t("PIN o Código Incorrecto"),
                body: _t("El PIN ingresado no coincide con ningún gerente autorizado ni es un código temporal válido."),
            });
            return false;
        }

        return false;
    }
});
