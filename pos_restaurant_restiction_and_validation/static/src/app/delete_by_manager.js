/*@odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { _t } from "@web/core/l10n/translation";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { patch } from "@web/core/utils/patch";
import { DenyPopup } from "../screens/popUps/deny_popUp";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

console.log("[Security] Módulo de eliminación de órdenes con soporte OTP cargado");

patch(PosStore.prototype, {
    async confirm1(selected_manager, order) {
        const manager = selected_manager ? selected_manager.id : false;
        const cashier1 = this.cashier.id;
        const session_id = this.config.current_session_id.id;
        const state = 'order_deleted';
        const receipt = order ? order.uuid : false;
        const order_num = order ? order.tracking_number : false;

        await this.env.services.orm.call("manager.approval", "getting_all_data", [{
            session_id,
            manager,
            cashier1,
            state,
            receipt,
            order_num,
        }]);
    },

    _checkIfNeedsManagerApproval() {
        if (!this.config.enable_pos_restaurant_restiction || !this.config.enable_restriction_on_order_delete) {
            return false;
        }
        return this.cashier?._role === 'cashier';
    },

    async _requestManagerApproval(order) {
        const orderName = order ? (order.name || order.tracking_number || _t("Orden")) : _t("Orden");
        const total = order ? order.get_total_with_tax() : 0;
        const details = _t("Cancelación de ticket completo: %s (Total: $%s)", orderName, total);

        // 1. Mostrar diálogo con opción de PIN o Código OTP Remoto
        const actionChoice = await makeAwaitable(this.dialog, DenyPopup, {
            title: _t("Autorización Requerida"),
            body: _t("Para descartar y eliminar el ticket \"%s\" ($%s) se requiere autorización de gerencia.", orderName, total),
            confirmText: _t("Ingresar PIN"),
            requestOtpText: _t("Solicitar Código Remoto"),
            showRequestOtp: true,
        });

        if (!actionChoice) {
            return false;
        }

        // 2. Opción OTP Remoto
        if (actionChoice === 'request_otp') {
            let otpRes;
            try {
                otpRes = await this.env.services.orm.call("pos.approval.otp", "action_request_otp", [{
                    config_id: this.config.id,
                    session_id: this.config.current_session_id.id,
                    cashier_id: this.cashier?.id,
                    action_type: 'order_deleted',
                    details: details,
                    receipt_number: order ? order.uuid : '',
                    order_number: order ? order.tracking_number : '',
                }]);
            } catch (err) {
                await this.env.services.dialog.add(AlertDialog, {
                    title: _t("Error de Comunicación"),
                    body: _t("No se pudo solicitar el código: ") + (err.message || err),
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

            await this.env.services.dialog.add(AlertDialog, {
                title: _t("Código Temporal Enviado"),
                body: _t("Se ha enviado un código de autorización al correo: %s.\nVigencia: %s minutos. Solicite el código al gerente e ingréselo a continuación.", otpRes.email, otpRes.validity_minutes),
            });

            const enteredOtp = await makeAwaitable(this.dialog, NumberPopup, {
                formatDisplayedValue: (x) => x,
                title: _t("Ingrese Código Temporal OTP (6 dígitos)"),
                startingValue: '',
            });

            if (!enteredOtp) {
                return false;
            }

            const validation = await this.env.services.orm.call("pos.approval.otp", "validate_approval", [
                this.config.id,
                this.config.current_session_id.id,
                enteredOtp,
                'order_deleted',
                details,
                this.cashier?.id,
                order ? order.uuid : '',
                order ? order.tracking_number : '',
            ]);

            if (validation && validation.approved) {
                return true;
            }

            await this.env.services.dialog.add(AlertDialog, {
                title: _t("Código Inválido"),
                body: validation?.message || _t("El código temporal no es válido o ya expiró."),
            });
            return false;
        }

        // 3. Opción PIN Fijo
        if (actionChoice === 'enter_pin') {
            const enteredPin = await makeAwaitable(this.dialog, NumberPopup, {
                formatDisplayedValue: (x) => x.replace(/./g, "•"),
                title: _t("Ingrese PIN del Gerente o Código"),
                startingValue: '',
            });

            if (!enteredPin) {
                return false;
            }

            if (this.models["hr.employee"]) {
                const employeesList = this.models["hr.employee"].getAll().filter(
                    (employee) => employee._role === "manager"
                );
                const matchedManager = employeesList.find(emp => emp._pin && emp._pin === Sha1.hash(enteredPin));
                if (matchedManager) {
                    await this.confirm1(matchedManager, order);
                    return true;
                }
            }

            // Validar en backend (OTP o manager)
            const validation = await this.env.services.orm.call("pos.approval.otp", "validate_approval", [
                this.config.id,
                this.config.current_session_id.id,
                enteredPin,
                'order_deleted',
                details,
                this.cashier?.id,
                order ? order.uuid : '',
                order ? order.tracking_number : '',
            ]);

            if (validation && validation.approved) {
                return true;
            }

            await this.env.services.dialog.add(AlertDialog, {
                title: _t("PIN o Código Incorrecto"),
                body: _t("El PIN ingresado no es válido."),
            });
            return false;
        }

        return false;
    },

    async onDeleteOrder(order) {
        const needsApproval = this._checkIfNeedsManagerApproval();

        if (needsApproval) {
            const approved = await this._requestManagerApproval(order);
            if (!approved) {
                return;
            }
        } else if (this.config.enable_pos_restaurant_restiction && this.config.enable_restriction_on_order_delete) {
            // Si el usuario actual ya es manager, solicita su propio PIN para confirmar
            const manager = this.cashier;
            if (!manager?._pin) {
                await this.env.services.dialog.add(AlertDialog, {
                    title: _t("PIN no configurado"),
                    body: _t("Necesitas configurar tu PIN para realizar esta acción."),
                });
                return;
            }

            const payload = await makeAwaitable(this.dialog, NumberPopup, {
                formatDisplayedValue: (x) => x.replace(/./g, "•"),
                title: _t("Confirmar con PIN"),
                startingValue: '',
            });

            if (!payload) {
                return;
            }

            const isPinValid = manager._pin === Sha1.hash(payload);
            if (!isPinValid) {
                await this.env.services.dialog.add(AlertDialog, {
                    title: _t("PIN incorrecto"),
                    body: _t("El PIN ingresado no es correcto."),
                });
                return;
            }

            await this.confirm1(manager, order);
        }

        await super.onDeleteOrder(...arguments);
    },
});
