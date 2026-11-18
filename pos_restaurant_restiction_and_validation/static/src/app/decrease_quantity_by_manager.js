/*@odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { DenyPopup } from "../screens/popUps/deny_popUp";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

console.log("[Security] Módulo de quitar lineas cargado");

patch(OrderSummary.prototype, {

    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },

    async confirm(selected_manager) {
        const manager = selected_manager.id;
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
            title: _t("Ingrese PIN"),
            startingValue: '',
        });

        if (!payload) {
            return false;
        }

        const isPinValid = manager._pin === Sha1.hash(payload);

        if (isPinValid) {
            await this.confirm(manager);
            return true;
        }

        await this.env.services.dialog.add(AlertDialog, {
            title: _t("PIN incorrecto"),
            body: _t("El PIN ingresado no es correcto."),
        });
        return false;
    },

    async updateSelectedOrderline({ buffer, key }) {
        const order = this.pos.getOrder();
        const selectedLine = order.getSelectedOrderline();

        if (key === 'Backspace') {
            if (!selectedLine) {
                // Si no hay línea seleccionada, llamar al método padre
                return super.updateSelectedOrderline(...arguments);
            }

            // Obtenemos el producto de la línea seleccionada
            const product = selectedLine.getProduct();
            if (!product) {
                // Si no hay producto, llamar al método padre
                return super.updateSelectedOrderline(...arguments);
            }

            // Verificamos si necesitamos aprobación del manager
            const needsApproval = this._checkIfNeedsManagerApproval(order, product.id);

            if (needsApproval) {
                const approved = await this._requestManagerApproval(product);
                if (!approved) {
                    // Si no se aprueba, NO llamar al método padre
                    return;
                }
            }

            // Si llegamos aquí, procedemos a eliminar la línea
            order.removeOrderline(selectedLine);
            // NO llamar a super.updateSelectedOrderline aquí porque ya eliminamos manualmente
            return;
        }

        // Para cualquier otra tecla que no sea Backspace, llamar al método padre
        return super.updateSelectedOrderline(...arguments);
    },

    _checkIfNeedsManagerApproval(order, productId) {
        // Verificar si el usuario actual es cashier (necesita aprobación)
        if (this.pos.accessRight.cashier?._role !== 'cashier') {
            return false;
        }

        // Verificar si hay líneas en la orden
        const orderlines = order.getOrderlines();
        if (!orderlines.length) {
            return false;
        }

        // Verificar si el producto está en las líneas actuales
        const productExists = orderlines.some(line => {
            const lineProduct = line.getProduct();
            return lineProduct && lineProduct.id === productId;
        });

        return productExists;
    },

    async _requestManagerApproval(product) {
        // Mostrar popup de advertencia
        const payload = await makeAwaitable(this.dialog, DenyPopup, {
            title: _t("Acción no autorizada"),
            body: _t("Necesitas aprobación del manager para eliminar este producto."),
        });

        if (!payload) {
            return false;
        }

        // Obtener lista de managers disponibles
        const employeesList = this.pos.config.advanced_employee_ids;
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
    }

});
