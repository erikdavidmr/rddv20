/*@odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { _t } from "@web/core/l10n/translation";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { patch } from "@web/core/utils/patch";
import { DenyPopup } from "../screens/popUps/deny_popUp";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

console.log("[Security] Módulo de eliminación de órdenes cargado");

patch(PosStore.prototype, {

    async confirm1(selected_manager) {
        const manager = selected_manager.id;
        const cashier1 = this.cashier.id;
        const session_id = this.config.current_session_id.id;
        const state = 'order_deleted';

        await this.env.services.orm.call("manager.approval", "getting_all_data", [{
            session_id,
            manager,
            cashier1,
            state,
        }]);
    },

    async passwordPopup(manager) {
        if (!manager?._pin) {
            await this.env.services.dialog.add(AlertDialog, {
                title: _t("PIN no configurado"),
                body: _t("Este manager no tiene PIN configurado."),
            });
            return false;
        }

        const payload = await makeAwaitable(this.dialog, NumberPopup, {
            formatDisplayedValue: (x) => x.replace(/./g, "•"),
            title: _t("Ingrese PIN del Manager"),
            startingValue: '',
        });

        if (!payload) {
            return false;
        }

        const isPinValid = manager._pin === Sha1.hash(payload);

        if (isPinValid) {
            await this.confirm1(manager);
            return true;
        }

        await this.env.services.dialog.add(AlertDialog, {
            title: _t("PIN incorrecto"),
            body: _t("El PIN ingresado no es correcto."),
        });
        return false;
    },

    _checkIfNeedsManagerApproval() {
        // Verificar si el usuario actual es cashier (necesita aprobación)
        return this.cashier._role === 'cashier';
    },

    async _requestManagerApproval() {
        // Mostrar popup de advertencia
        const payload = await makeAwaitable(this.dialog, DenyPopup, {
            title: _t("Acción no autorizada"),
            body: _t("No estás autorizado para eliminar la orden. Necesitas aprobación del manager."),
        });

        if (!payload) {
            return false;
        }

        // Obtener lista de managers disponibles
        const employeesList = this.models["hr.employee"].getAll().filter(
            (employee) => employee._role === "manager"
        );
        if (!employeesList?.length) {
            await this.env.services.dialog.add(AlertDialog, {
                title: _t("Manager no disponible"),
                body: _t("No hay managers disponibles en este momento."),
            });
            return false;
        }

        // Seleccionar manager
        const manager = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Seleccionar Manager"),
            list: employeesList.map(emp => ({
                id: emp.id,
                item: emp,
                label: emp.name,
            })),
        });

        if (!manager) {
            return false;
        }

        // Validar PIN del manager
        return await this.passwordPopup(manager);
    },

    async onDeleteOrder(order) {
        // Verificar si necesita aprobación del manager
        const needsApproval = this._checkIfNeedsManagerApproval();

        if (needsApproval) {
            // Solicitar aprobación del manager
            const approved = await this._requestManagerApproval();
            if (!approved) {
                // Si no se aprueba, salir sin eliminar
                return;
            }
        } else {
            // Si es manager, verificar su PIN
            const manager = this.cashier;
            
            if (!manager._pin) {
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

            // Confirmar la acción del manager
            await this.confirm1(manager);
        }

        // Si llegamos aquí, proceder con la eliminación
        await super.onDeleteOrder(...arguments);
    },
});
