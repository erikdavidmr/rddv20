/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

patch(OrderSummary.prototype, {
    async ProductUomMultiButton(line) {
        const order = this.pos.getOrder();
        if (!order) return;

        const targetLine = line || order.getSelectedOrderline();
        if (!targetLine) return;

        const product = targetLine.product_id;
        if (!product?.multi_uom_price_ids?.length) return;

        // ✅ SIEMPRE tomar la pricelist del pedido actual
        const pricelist = order.pricelist_id;
        const qty = targetLine.getQuantity() || 1;

        // Resolver UoM real desde el store
        const uomModel = targetLine.models?.["uom.uom"];
        const getUomId = (u) => (Array.isArray(u) ? u[0] : (typeof u === "object" ? u.id : u));

        const resolveUom = (u) => {
            if (!u) return null;
            const id = getUomId(u);
            if (!id) return typeof u === "object" ? u : null;
            if (uomModel?.get) return uomModel.get(id) || (typeof u === "object" ? u : null);
            return typeof u === "object" ? u : null;
        };

        // ✅ Preview usando el MISMO cálculo final (sin duplicar lógica)
        const previewForUom = (uom) => {
            const prev = targetLine.uom_id;
            try {
                targetLine.uom_id = uom;
                if (typeof targetLine._calculatePriceForSelectedUom === "function") {
                    return targetLine._calculatePriceForSelectedUom(qty, pricelist);
                }
                // fallback mínimo (idealmente siempre existe el helper)
                const extra = targetLine.getPriceExtra ? targetLine.getPriceExtra() : 0;
                return product.getPrice(pricelist, qty, extra, false, product);
            } finally {
                targetLine.uom_id = prev;
            }
        };

        const currentUom = resolveUom(targetLine.uom_id) || resolveUom(product.uom_id);

        // Map para recuperar UoM por id (cuando popup devuelve {id, item})
        const uomById = {};

        const uomList = product.multi_uom_price_ids
            .map((multi) => {
                const uom = resolveUom(multi.uom_id);
                if (!uom) return null;

                uomById[uom.id] = uom;

                return {
                    id: uom.id,
                    label: `${this.env.utils.formatCurrency(previewForUom(uom))} (${uom.name})`,
                    isSelected: currentUom?.id === uom.id,
                    item: multi, // compat: SelectionPopup puede devolver este wrapper
                };
            })
            .filter(Boolean);

        if (!uomList.length) return;

        const selected = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("UOM"),
            list: uomList,
        });
        if (!selected) return;

        // ✅ SelectionPopup puede devolver:
        // - wrapper {id, item}
        // - o el multi_uom_line directo (raro)
        const selectedId =
            selected?.id ||
            getUomId(selected?.uom_id) ||
            getUomId(selected?.item?.uom_id);

        const selectedUom =
            uomById[selectedId] ||
            resolveUom(selected?.uom_id) ||
            resolveUom(selected?.item?.uom_id);

        if (!selectedUom) return;

        // ✅ Aplicar UoM
        targetLine.uom_id = selectedUom;

        // ✅ Reaplicar qty con redondeo según la nueva UoM (sin recalcular precio aquí)
        if (typeof targetLine.setQuantity === "function") {
            targetLine.setQuantity(targetLine.getQuantity(), true);
        }

        // ✅ Calcular precio final unitario con la pricelist actual
        const finalPrice =
            typeof targetLine._calculatePriceForSelectedUom === "function"
                ? targetLine._calculatePriceForSelectedUom(targetLine.getQuantity(), pricelist)
                : previewForUom(selectedUom);

        targetLine.setUnitPrice(finalPrice);

        // ✅ MUY IMPORTANTE: no dejarla como "manual", para que cambios de cliente/pricelist sigan aplicando
        if ("price_type" in targetLine) {
            targetLine.price_type = "original";
        }

    },

    // Sobrescribir setLinePrice para permitir cambios sin validación, pero manteniendo "original"
    async setLinePrice(line, price) {
        if (line?.product_id?.multi_uom_price_ids?.length) {
            line.setUnitPrice(price);
            if ("price_type" in line) {
                line.price_type = "original";
            }
            line.setDirty?.();
            return;
        }
        await super.setLinePrice(line, price);
    },
});
