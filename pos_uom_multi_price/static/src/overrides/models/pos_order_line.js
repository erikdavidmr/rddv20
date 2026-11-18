/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { _t } from "@web/core/l10n/translation";
import { localization as l10n } from "@web/core/l10n/localization";
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

// Normaliza retornos raros de getPrice (a veces te llega object/proxy)
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
        if (!this.uom_id) return super.quantityStr;

        const unit = this.uom_id;
        const dp = this.models["decimal.precision"].find((d) => d.name === "Product Unit");
        const decimals = dp?.digits ?? 2;
        const decimalPoint = l10n.decimalPoint;
        let unitPart = "" + this.qty;
        let decimalPart = "";

        if (unit.rounding && unit.rounding < 1 && decimals) {
            const formatted = formatFloat(this.qty, { digits: [69, decimals] });
            [unitPart, decimalPart = ""] = formatted.split(decimalPoint);
        } else if (unit.rounding && unit.rounding >= 1) {
            unitPart = this.qty.toFixed(0);
        }
        return {
            qtyStr: unitPart + (decimalPart ? decimalPoint + decimalPart : ""),
            unitPart,
            decimalPoint,
            decimalPart,
        };
    },

    getUnitPrice() {
        const digits = this.models["decimal.precision"].find((dp) => dp.name === "Product Price").digits;
        return window.parseFloat(roundDecimals(this.price_unit || 0, digits).toFixed(digits));
    },

    setUnitPrice(price) {
        super.setUnitPrice(price);
        this.setDirty();
    },

    _calculatePriceForSelectedUom(quantity, pricelistOverride = null) {
        const qtySelected = typeof quantity === "number" ? quantity : this.getQuantity();
        const safeQty = qtySelected || 1;

        const pricelist = pricelistOverride || this.order_id?.pricelist_id;
        const priceExtra = this.getPriceExtra ? this.getPriceExtra() : 0;

        const productUom = resolveUomFromStore(this.models, this.product_id?.uom_id);
        const lineUom = resolveUomFromStore(this.models, this.uom_id) || productUom;

        // Base / mismo uom
        if (!lineUom || !productUom || lineUom.id === productUom.id) {
            const prevUom = this.uom_id;
            try {
                this.uom_id = productUom || prevUom;
                return toNumberPrice(this.product_id.getPrice(pricelist, safeQty, priceExtra, false, this.product_id));
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
                return toNumberPrice(this.product_id.getPrice(pricelist, qtyForPricing, priceExtra, false, this.product_id));
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

    isPosGroupable() {
        if (this.uom_id) {
            const unit_groupable = this.uom_id?.is_pos_groupable || false;
            return unit_groupable && !this.isPartOfCombo();
        }
        return super.isPosGroupable(...arguments);
    },

    getDisplayData() {
        if (this.uom_id) {
            return { ...super.getDisplayData(), unit: this.uom_id.name };
        }
        return super.getDisplayData();
    },

    getUnit() {
        return this.uom_id || super.getUnit(...arguments);
    },

    setQuantity(quantity, keep_price) {
        this.order_id.assertEditable();

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
            const maxQtyToRefund = refundDetails.line.qty - refundDetails.line.refundedQty;
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
                const dp = this.models["decimal.precision"].find((d) => d.name === "Product Unit");
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
            const newPrice = this._calculatePriceForSelectedUom(this.getQuantity());
            this.setUnitPrice(newPrice);
        }

        this.setDirty();
        return true;
    },

    canBeMergedWith(orderline) {
        const isSameUom = this.uom_id?.id === orderline.uom_id?.id;
        return super.canBeMergedWith(orderline) && isSameUom;
    },
});

// =====================
//  PATCH PosOrder
// =====================

// helper interno: recomputa SOLO líneas "original" no combo
function recompute_original_lines(order, pricelist) {
    const pl = pricelist || order.pricelist_id;

    // Odoo a veces expone lines como collection; preferimos get_orderlines si existe
    const rawLines = order.lines;
    const lines = Array.isArray(rawLines) ? rawLines : (rawLines ? Array.from(rawLines) : []);

    const lines_to_recompute = lines.filter(
        (line) =>
            line &&
            line.price_type === "original" &&
            !(line.combo_line_ids?.length || line.combo_parent_id)
    );

    for (const line of lines_to_recompute) {
        const newPrice = line._calculatePriceForSelectedUom(line.getQuantity(), pl);
        line.setUnitPrice(newPrice);

        if ("price_type" in line) line.price_type = "original";

        line.setDirty?.();
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

    setPricelist(pricelist) {
        const result = super.setPricelist(...arguments);
        scheduleRecompute(this, pricelist || this.pricelist_id);
        return result;
    },
});
