/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { _t } from "@web/core/l10n/translation";
import { formatFloat, roundDecimals, roundPrecision } from "@web/core/utils/numbers";

// =====================
//  HELPERS (local)
// =====================
function getM2OId(v) {
    return Array.isArray(v) ? v[0] : (typeof v === "object" ? v?.id : v);
}

// ✅ “cantidad de unidades de referencia por 1 unidad de esta UoM”
// Ej: referencia=gramo => gramo.factor_inv=1, paq1kg.factor_inv=1000
function uomFactorInv(u) {
    if (!u) return 1;
    if (u.factor_inv != null && u.factor_inv !== 0) return u.factor_inv;
    if (u.factor != null && u.factor !== 0) return 1 / u.factor;
    return 1;
}

function resolveUomFromStore(models, u) {
    if (!u) return null;
    const uomModel = models?.["uom.uom"];
    const id = getM2OId(u);
    if (uomModel?.get && id) return uomModel.get(id) || (typeof u === "object" ? u : null);
    return typeof u === "object" ? u : null;
}

// Normaliza retornos raros de get_price (a veces te llega object/proxy)
function toNumberPrice(v) {
    if (typeof v === "number") return isNaN(v) ? 0 : v;
    if (typeof v === "string") {
        const n = parseFloat(v);
        return isNaN(n) ? 0 : n;
    }
    if (v && typeof v === "object") {
        if (typeof v.price === "number") return isNaN(v.price) ? 0 : v.price;
        if (typeof v.price_unit === "number") return isNaN(v.price_unit) ? 0 : v.price_unit;
        if (typeof v.unit_price === "number") return isNaN(v.unit_price) ? 0 : v.unit_price;
        if (typeof v.value === "number") return isNaN(v.value) ? 0 : v.value;

        if (typeof v.price === "string") return parseFloat(v.price) || 0;
        if (typeof v.price_unit === "string") return parseFloat(v.price_unit) || 0;
    }
    return 0;
}

// microtask helper (para correr DESPUÉS de que OWL/Odoo termine sus updates)
function microtask(fn) {
    if (typeof queueMicrotask === "function") return queueMicrotask(fn);
    return Promise.resolve().then(fn);
}

// =====================
//  CONFIG (solo POS)
// =====================
const BULK_MIN_QTY_FLOOR = 0.01; // mínimo en UoM del PRODUCTO (Paq c/1kg)
const EPS = 1e-9;

// =====================
//  PATCH PosOrderline
// =====================
patch(PosOrderline.prototype, {
    setup() {
        super.setup(...arguments);

        const base = resolveUomFromStore(this.models, this.product_id?.uom_id);
        const current = resolveUomFromStore(this.models, this.uom_id);
        const refunded = resolveUomFromStore(this.models, this.refunded_orderline_id?.uom_id);

        this.uom_id = refunded || current || base;
    },

    clone() {
        const orderline = super.clone(...arguments);
        orderline.uom_id = this.uom_id;
        return orderline;
    },

    get quantityStr() {
        if (!this.uom_id) return super.quantityStr();

        const unit = this.uom_id;
        const dp = this.models["decimal.precision"].find((d) => d.name === "Product Unit of Measure");
        const decimals = dp?.digits ?? 2;

        if (unit.rounding && unit.rounding < 1) {
            return formatFloat(this.qty, { digits: [69, decimals] });
        }
        if (unit.rounding && unit.rounding >= 1) {
            return this.qty.toFixed(0);
        }
        return "" + this.qty;
    },

    setLinePrice() {
        const prices = this.get_all_prices();
        if (this.price_subtotal !== prices.priceWithoutTax) {
            this.price_subtotal = prices.priceWithoutTax;
        }
        if (this.price_subtotal_incl !== prices.priceWithTax) {
            this.price_subtotal_incl = prices.priceWithTax;
        }
    },

    get_unit_price() {
        const digits = this.models["decimal.precision"].find((dp) => dp.name === "Product Price").digits;
        return window.parseFloat(roundDecimals(this.price_unit || 0, digits).toFixed(digits));
    },

    set_unit_price(price) {
        const parsed = typeof price === "number" ? price : window.parseFloat("" + price);
        const safe = isNaN(parsed) ? 0 : parsed;

        this.price_unit = roundDecimals(
            safe,
            this.models["decimal.precision"].find((dp) => dp.name === "Product Price").digits
        );

        this.setDirty();
    },

    get_unit_display_price() {
        if (this.config.iface_tax_included === "total") {
            return this.get_all_prices(1).priceWithTax;
        }
        return this.get_all_prices(1).priceWithoutTax;
    },

    _calculatePriceForSelectedUom(quantity, pricelistOverride = null) {
        const qtySelected = typeof quantity === "number" ? quantity : this.get_quantity();
        const safeQty = qtySelected || 1;

        const pricelist = pricelistOverride || this.order_id?.pricelist_id;
        const priceExtra = this.get_price_extra ? this.get_price_extra() : 0;

        const productUom = resolveUomFromStore(this.models, this.product_id?.uom_id);
        const lineUom = resolveUomFromStore(this.models, this.uom_id) || productUom;

        // Base / mismo uom
        if (!lineUom || !productUom || lineUom.id === productUom.id) {
            const prevUom = this.uom_id;
            try {
                this.uom_id = productUom || prevUom;
                return toNumberPrice(this.product_id.get_price(pricelist, safeQty, priceExtra, safeQty));
            } finally {
                this.uom_id = prevUom;
            }
        }

        // Ratio usando factor_inv
        const lineInv = uomFactorInv(lineUom);       // gramo => 1
        const productInv = uomFactorInv(productUom); // paq1kg => 1000
        const ratioLineToProduct = lineInv / productInv; // 1/1000 = 0.001 (gramo->paq)

        const qtyInProductUom = safeQty * ratioLineToProduct;

        const computeUnitProduct = (qtyForPricing) => {
            const prevUom = this.uom_id;
            try {
                this.uom_id = productUom; // evita doble conversión en POS
                return toNumberPrice(this.product_id.get_price(pricelist, qtyForPricing, priceExtra, qtyForPricing));
            } finally {
                this.uom_id = prevUom;
            }
        };

        // ✅ CLAMP: si la UoM de la línea es más pequeña (ratio < 1) y qty cae debajo del mínimo,
        // calcular con 0.01 para evitar fallback 0.00
        const lineIsSmallerThanProduct = ratioLineToProduct < 1;
        const qtyForPricing =
            lineIsSmallerThanProduct && qtyInProductUom < BULK_MIN_QTY_FLOOR
                ? BULK_MIN_QTY_FLOOR
                : qtyInProductUom;

        let unitProduct = computeUnitProduct(qtyForPricing);

        // Salvavidas extra (por si get_price todavía regresa 0)
        if (!unitProduct || Math.abs(unitProduct) < EPS) {
            unitProduct = computeUnitProduct(BULK_MIN_QTY_FLOOR);
        }
        if (!unitProduct || Math.abs(unitProduct) < EPS) {
            unitProduct = computeUnitProduct(1);
        }

        // Convertir a unitario en la UoM de la línea
        return unitProduct * ratioLineToProduct;
    },

    get_quantity_str_with_unit() {
        if (this.uom_id) {
            const unit = this.uom_id;
            if (this.is_pos_groupable()) {
                return this.quantityStr + " " + unit.name;
            }
            return this.quantityStr;
        }
        return super.get_quantity_str_with_unit();
    },

    is_pos_groupable() {
        if (this.uom_id) {
            const unit_groupable = this.uom_id?.is_pos_groupable || false;
            return unit_groupable && !this.isPartOfCombo();
        }
        return super.is_pos_groupable();
    },

    getDisplayData() {
        if (this.uom_id) {
            return { ...super.getDisplayData(), unit: this.uom_id.name };
        }
        return super.getDisplayData();
    },

    get_unit() {
        return this.uom_id || super.get_unit(...arguments);
    },

    set_quantity(quantity, keep_price) {
        this.order_id.assert_editable();

        const quant =
            typeof quantity === "number"
                ? quantity
                : window.parseFloat("" + (quantity ? quantity : 0));

        const allLineToRefundUuids = this.models["pos.order"].reduce((acc, order) => {
            Object.assign(acc, order.uiState.lineToRefund);
            return acc;
        }, {});

        if (this.refunded_orderline_id?.uuid in allLineToRefundUuids) {
            const refundDetails = allLineToRefundUuids[this.refunded_orderline_id.uuid];
            const maxQtyToRefund = refundDetails.line.qty - refundDetails.line.refunded_qty;
            if (quant > 0) {
                return {
                    title: _t("Positive quantity not allowed"),
                    body: _t(
                        "Only a negative quantity is allowed for this refund line. Click on +/- to modify the quantity to be refunded."
                    ),
                };
            } else if (quant == 0) {
                refundDetails.qty = 0;
            } else if (-quant <= maxQtyToRefund) {
                refundDetails.qty = -quant;
            } else {
                return {
                    title: _t("Greater than allowed"),
                    body: _t("The requested quantity to be refunded is higher than the refundable quantity."),
                };
            }
        }

        const unit = this.uom_id || this.product_id.uom_id;
        if (unit) {
            if (unit.rounding) {
                const dp = this.models["decimal.precision"].find((d) => d.name === "Product Unit of Measure");
                const decimals = dp?.digits ?? 2;
                const rounding = Math.max(unit.rounding, Math.pow(10, -decimals));
                this.qty = roundPrecision(quant, rounding);
            } else {
                this.qty = roundPrecision(quant, 1);
            }
        } else {
            this.qty = quant;
        }

        if (!keep_price && this.price_type === "original") {
            const newPrice = this._calculatePriceForSelectedUom(this.get_quantity());
            this.set_unit_price(newPrice);
        }

        this.setDirty();
        return true;
    },

    can_be_merged_with(orderline) {
        const isSameCustomerNote =
            (Boolean(orderline.get_customer_note()) === false && Boolean(this.get_customer_note()) === false) ||
            orderline.get_customer_note() === this.get_customer_note();

        const isSameUom = this.uom_id?.id === orderline.uom_id?.id;

        return (
            !this.skip_change &&
            orderline.getNote() === this.getNote() &&
            this.get_product().id === orderline.get_product().id &&
            this.is_pos_groupable() &&
            this.get_discount() === 0 &&
            !this.isLotTracked() &&
            this.full_product_name === orderline.full_product_name &&
            isSameCustomerNote &&
            !this.refunded_orderline_id &&
            !orderline.isPartOfCombo() &&
            isSameUom
        );
    },
});

// =====================
//  PATCH PosOrder
// =====================

// helper interno: recomputa SOLO líneas "original" no combo
function recompute_original_lines(order, pricelist) {
    const pl = pricelist || order.pricelist_id;

    // Odoo a veces expone lines como collection; preferimos get_orderlines si existe
    const rawLines = typeof order.get_orderlines === "function" ? order.get_orderlines() : order.lines;
    const lines = Array.isArray(rawLines) ? rawLines : (rawLines ? Array.from(rawLines) : []);

    const lines_to_recompute = lines.filter(
        (line) =>
            line &&
            line.price_type === "original" &&
            !(line.combo_line_ids?.length || line.combo_parent_id)
    );

    for (const line of lines_to_recompute) {
        const newPrice = line._calculatePriceForSelectedUom(line.get_quantity(), pl);
        line.set_unit_price(newPrice);

        if ("price_type" in line) line.price_type = "original";

        line.setDirty?.();
        line.setLinePrice?.();
    }
}

// ✅ ejecutar recálculo “al final” para que Odoo no lo pise después
function scheduleRecompute(order, pricelist) {
    if (order.__multi_uom_pl_recompute_scheduled) return;
    order.__multi_uom_pl_recompute_scheduled = true;

    microtask(() => {
        order.__multi_uom_pl_recompute_scheduled = false;
        recompute_original_lines(order, pricelist || order.pricelist_id);
    });
}

patch(PosOrder.prototype, {
    update(values) {
        const oldPlId = getM2OId(this.pricelist_id);
        const res = super.update(...arguments);

        if (
            values &&
            Object.prototype.hasOwnProperty.call(values, "pricelist_id") &&
            !this.__skip_pricelist_recompute
        ) {
            const newPlId = getM2OId(this.pricelist_id);
            if (oldPlId !== newPlId) {
                // 👇 NO recalcular directo, programarlo al final
                scheduleRecompute(this, this.pricelist_id);
            }
        }
        return res;
    },

    set_pricelist(pricelist) {
        // Evitar doble recálculo (porque set_pricelist llama update y update() detecta cambios)
        this.__skip_pricelist_recompute = true;
        this.update({ pricelist_id: pricelist || false });
        this.__skip_pricelist_recompute = false;

        // 👇 programar al final
        scheduleRecompute(this, pricelist || this.pricelist_id);
    },
});

// =====================
//  HOOK: cuando POS cambia pricelist por línea, recalcular líneas con UoM alterna
// =====================
if (PosOrderline.prototype.set_pricelist) {
    patch(PosOrderline.prototype, {
        set_pricelist(pricelist) {
            const res = super.set_pricelist(...arguments);

            // 👇 al final, por si Odoo recalcula después
            microtask(() => {
                try {
                    const productUom = resolveUomFromStore(this.models, this.product_id?.uom_id);
                    const lineUom = resolveUomFromStore(this.models, this.uom_id);

                    const isAltUom =
                        productUom &&
                        lineUom &&
                        productUom.id &&
                        lineUom.id &&
                        productUom.id !== lineUom.id;

                    const isOriginal = !("price_type" in this) || this.price_type === "original";

                    if (isAltUom && isOriginal && typeof this._calculatePriceForSelectedUom === "function") {
                        const qty = this.get_quantity() || 1;
                        const newPrice = this._calculatePriceForSelectedUom(qty, pricelist);
                        this.set_unit_price(newPrice);

                        if ("price_type" in this) this.price_type = "original";

                        this.setDirty?.();
                        this.setLinePrice?.();
                    }
                } catch (e) {
                    // no romper POS
                }
            });

            return res;
        },
    });
}


///** @odoo-module */
//
//import { patch } from "@web/core/utils/patch";
//import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
//import { PosOrder } from "@point_of_sale/app/models/pos_order";
//import { _t } from "@web/core/l10n/translation";
//import { formatFloat, roundDecimals, roundPrecision } from "@web/core/utils/numbers";
//
//// =====================
////  HELPERS (local)
//// =====================
//function getM2OId(v) {
//    return Array.isArray(v) ? v[0] : (typeof v === "object" ? v?.id : v);
//}
//
//// ✅ “cantidad de unidades de referencia por 1 unidad de esta UoM”
//// Ej: referencia=gramo => gramo.factor_inv=1, paq1kg.factor_inv=1000
//function uomFactorInv(u) {
//    if (!u) return 1;
//    if (u.factor_inv != null && u.factor_inv !== 0) return u.factor_inv;
//    if (u.factor != null && u.factor !== 0) return 1 / u.factor;
//    return 1;
//}
//
//function resolveUomFromStore(models, u) {
//    if (!u) return null;
//    const uomModel = models?.["uom.uom"];
//    const id = getM2OId(u);
//    if (uomModel?.get && id) return uomModel.get(id) || (typeof u === "object" ? u : null);
//    return typeof u === "object" ? u : null;
//}
//
//// Normaliza retornos raros de get_price (a veces te llega object/proxy)
//function toNumberPrice(v) {
//    if (typeof v === "number") return isNaN(v) ? 0 : v;
//    if (typeof v === "string") {
//        const n = parseFloat(v);
//        return isNaN(n) ? 0 : n;
//    }
//    if (v && typeof v === "object") {
//        if (typeof v.price === "number") return isNaN(v.price) ? 0 : v.price;
//        if (typeof v.price_unit === "number") return isNaN(v.price_unit) ? 0 : v.price_unit;
//        if (typeof v.unit_price === "number") return isNaN(v.unit_price) ? 0 : v.unit_price;
//        if (typeof v.value === "number") return isNaN(v.value) ? 0 : v.value;
//
//        if (typeof v.price === "string") return parseFloat(v.price) || 0;
//        if (typeof v.price_unit === "string") return parseFloat(v.price_unit) || 0;
//    }
//    return 0;
//}
//
//// =====================
////  CONFIG (solo POS)
//// =====================
//const BULK_MIN_QTY_FLOOR = 0.01; // mínimo en UoM del PRODUCTO (Paq c/1kg)
//const EPS = 1e-9;
//
//// =====================
////  PATCH PosOrderline
//// =====================
//patch(PosOrderline.prototype, {
//    setup() {
//        super.setup(...arguments);
//
//        const base = resolveUomFromStore(this.models, this.product_id?.uom_id);
//        const current = resolveUomFromStore(this.models, this.uom_id);
//        const refunded = resolveUomFromStore(this.models, this.refunded_orderline_id?.uom_id);
//
//        this.uom_id = refunded || current || base;
//    },
//
//    clone() {
//        const orderline = super.clone(...arguments);
//        orderline.uom_id = this.uom_id;
//        return orderline;
//    },
//
//    get quantityStr() {
//        if (!this.uom_id) return super.quantityStr();
//
//        const unit = this.uom_id;
//        const dp = this.models["decimal.precision"].find((d) => d.name === "Product Unit of Measure");
//        const decimals = dp?.digits ?? 2;
//
//        if (unit.rounding && unit.rounding < 1) {
//            return formatFloat(this.qty, { digits: [69, decimals] });
//        }
//        if (unit.rounding && unit.rounding >= 1) {
//            return this.qty.toFixed(0);
//        }
//        return "" + this.qty;
//    },
//
//    setLinePrice() {
//        const prices = this.get_all_prices();
//        if (this.price_subtotal !== prices.priceWithoutTax) {
//            this.price_subtotal = prices.priceWithoutTax;
//        }
//        if (this.price_subtotal_incl !== prices.priceWithTax) {
//            this.price_subtotal_incl = prices.priceWithTax;
//        }
//    },
//
//    get_unit_price() {
//        const digits = this.models["decimal.precision"].find((dp) => dp.name === "Product Price").digits;
//        return window.parseFloat(roundDecimals(this.price_unit || 0, digits).toFixed(digits));
//    },
//
//    set_unit_price(price) {
//        const parsed = typeof price === "number" ? price : window.parseFloat("" + price);
//        const safe = isNaN(parsed) ? 0 : parsed;
//
//        this.price_unit = roundDecimals(
//            safe,
//            this.models["decimal.precision"].find((dp) => dp.name === "Product Price").digits
//        );
//
//        this.setDirty();
//    },
//
//    get_unit_display_price() {
//        if (this.config.iface_tax_included === "total") {
//            return this.get_all_prices(1).priceWithTax;
//        }
//        return this.get_all_prices(1).priceWithoutTax;
//    },
//
//    _calculatePriceForSelectedUom(quantity, pricelistOverride = null) {
//        const qtySelected = typeof quantity === "number" ? quantity : this.get_quantity();
//        const safeQty = qtySelected || 1;
//
//        const pricelist = pricelistOverride || this.order_id?.pricelist_id;
//        const priceExtra = this.get_price_extra ? this.get_price_extra() : 0;
//
//        const productUom = resolveUomFromStore(this.models, this.product_id?.uom_id);
//        const lineUom = resolveUomFromStore(this.models, this.uom_id) || productUom;
//
//        // Base / mismo uom
//        if (!lineUom || !productUom || lineUom.id === productUom.id) {
//            const prevUom = this.uom_id;
//            try {
//                this.uom_id = productUom || prevUom;
//                return toNumberPrice(this.product_id.get_price(pricelist, safeQty, priceExtra, safeQty));
//            } finally {
//                this.uom_id = prevUom;
//            }
//        }
//
//        // Ratio usando factor_inv
//        const lineInv = uomFactorInv(lineUom);       // gramo => 1
//        const productInv = uomFactorInv(productUom); // paq1kg => 1000
//        const ratioLineToProduct = lineInv / productInv; // 1/1000 = 0.001 (gramo->paq)
//
//        const qtyInProductUom = safeQty * ratioLineToProduct;
//
//        const computeUnitProduct = (qtyForPricing) => {
//            const prevUom = this.uom_id;
//            try {
//                this.uom_id = productUom; // evita doble conversión en POS
//                return toNumberPrice(this.product_id.get_price(pricelist, qtyForPricing, priceExtra, qtyForPricing));
//            } finally {
//                this.uom_id = prevUom;
//            }
//        };
//
//        // ✅ CLAMP: si la UoM de la línea es más pequeña (ratio < 1) y qty cae debajo del mínimo,
//        // SIEMPRE calcula con 0.01 para no caer al fallback raro que te da 0.00 por gramo.
//        const lineIsSmallerThanProduct = ratioLineToProduct < 1;
//        const qtyForPricing =
//            lineIsSmallerThanProduct && qtyInProductUom < BULK_MIN_QTY_FLOOR
//                ? BULK_MIN_QTY_FLOOR
//                : qtyInProductUom;
//
//        let unitProduct = computeUnitProduct(qtyForPricing);
//
//        // Salvavidas extra (por si get_price todavía regresa 0)
//        if (!unitProduct || Math.abs(unitProduct) < EPS) {
//            unitProduct = computeUnitProduct(BULK_MIN_QTY_FLOOR);
//        }
//        if (!unitProduct || Math.abs(unitProduct) < EPS) {
//            unitProduct = computeUnitProduct(1);
//        }
//
//        // Convertir a unitario en la UoM de la línea
//        return unitProduct * ratioLineToProduct;
//    },
//
//    get_quantity_str_with_unit() {
//        if (this.uom_id) {
//            const unit = this.uom_id;
//            if (this.is_pos_groupable()) {
//                return this.quantityStr + " " + unit.name;
//            }
//            return this.quantityStr;
//        }
//        return super.get_quantity_str_with_unit();
//    },
//
//    is_pos_groupable() {
//        if (this.uom_id) {
//            const unit_groupable = this.uom_id?.is_pos_groupable || false;
//            return unit_groupable && !this.isPartOfCombo();
//        }
//        return super.is_pos_groupable();
//    },
//
//    getDisplayData() {
//        if (this.uom_id) {
//            return { ...super.getDisplayData(), unit: this.uom_id.name };
//        }
//        return super.getDisplayData();
//    },
//
//    get_unit() {
//        return this.uom_id || super.get_unit(...arguments);
//    },
//
//    set_quantity(quantity, keep_price) {
//        this.order_id.assert_editable();
//
//        const quant =
//            typeof quantity === "number"
//                ? quantity
//                : window.parseFloat("" + (quantity ? quantity : 0));
//
//        const allLineToRefundUuids = this.models["pos.order"].reduce((acc, order) => {
//            Object.assign(acc, order.uiState.lineToRefund);
//            return acc;
//        }, {});
//
//        if (this.refunded_orderline_id?.uuid in allLineToRefundUuids) {
//            const refundDetails = allLineToRefundUuids[this.refunded_orderline_id.uuid];
//            const maxQtyToRefund = refundDetails.line.qty - refundDetails.line.refunded_qty;
//            if (quant > 0) {
//                return {
//                    title: _t("Positive quantity not allowed"),
//                    body: _t(
//                        "Only a negative quantity is allowed for this refund line. Click on +/- to modify the quantity to be refunded."
//                    ),
//                };
//            } else if (quant == 0) {
//                refundDetails.qty = 0;
//            } else if (-quant <= maxQtyToRefund) {
//                refundDetails.qty = -quant;
//            } else {
//                return {
//                    title: _t("Greater than allowed"),
//                    body: _t("The requested quantity to be refunded is higher than the refundable quantity."),
//                };
//            }
//        }
//
//        const unit = this.uom_id || this.product_id.uom_id;
//        if (unit) {
//            if (unit.rounding) {
//                const dp = this.models["decimal.precision"].find((d) => d.name === "Product Unit of Measure");
//                const decimals = dp?.digits ?? 2;
//                const rounding = Math.max(unit.rounding, Math.pow(10, -decimals));
//                this.qty = roundPrecision(quant, rounding);
//            } else {
//                this.qty = roundPrecision(quant, 1);
//            }
//        } else {
//            this.qty = quant;
//        }
//
//        if (!keep_price && this.price_type === "original") {
//            const newPrice = this._calculatePriceForSelectedUom(this.get_quantity());
//            this.set_unit_price(newPrice);
//        }
//
//        this.setDirty();
//        return true;
//    },
//
//    can_be_merged_with(orderline) {
//        const isSameCustomerNote =
//            (Boolean(orderline.get_customer_note()) === false && Boolean(this.get_customer_note()) === false) ||
//            orderline.get_customer_note() === this.get_customer_note();
//
//        const isSameUom = this.uom_id?.id === orderline.uom_id?.id;
//
//        return (
//            !this.skip_change &&
//            orderline.getNote() === this.getNote() &&
//            this.get_product().id === orderline.get_product().id &&
//            this.is_pos_groupable() &&
//            this.get_discount() === 0 &&
//            !this.isLotTracked() &&
//            this.full_product_name === orderline.full_product_name &&
//            isSameCustomerNote &&
//            !this.refunded_orderline_id &&
//            !orderline.isPartOfCombo() &&
//            isSameUom
//        );
//    },
//});
//
//// =====================
////  PATCH PosOrder
//// =====================
//patch(PosOrder.prototype, {
//    set_pricelist(pricelist) {
//        this.update({ pricelist_id: pricelist || false });
//
//        const lines_to_recompute = this.lines.filter(
//            (line) =>
//                line.price_type === "original" &&
//                !(line.combo_line_ids?.length || line.combo_parent_id)
//        );
//
//        for (const line of lines_to_recompute) {
//            const newPrice = line._calculatePriceForSelectedUom(line.get_quantity(), pricelist);
//            line.set_unit_price(newPrice);
//
//            if ("price_type" in line) line.price_type = "original";
//
//            line.setDirty?.();
//            line.setLinePrice?.();
//        }
//    },
//});