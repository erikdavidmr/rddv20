import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { _t } from "@web/core/l10n/translation";
import { findCardPricelist } from "@pos_card_surcharge_pricelist/app/utils/card_pricelist_utils";

patch(Navbar.prototype, {
    get isCardPricelistActive() {
        try {
            const order = this.pos?.getOrder?.();
            const pl = order?.pricelist_id;
            return pl ? Boolean(pl.is_special_td || (pl.name || "").includes("2.0")) : false;
        } catch {
            return false;
        }
    },

    get showCardSurchargeToggle() {
        try {
            return Boolean(this.pos?.config?.enable_card_surcharge && this.pos?.getOrder?.());
        } catch {
            return false;
        }
    },

    toggleCardPricelist() {
        const order = this.pos?.getOrder?.();
        if (!order) return;
        const notification = this.notification || this.pos?.notification;

        if (this.isCardPricelistActive) {
            // Regresar a lista de efectivo
            const cashPl = order.base_cash_pricelist_id || this.pos?.config?.pricelist_id;
            if (cashPl) {
                order.setPricelist(cashPl);
                if (notification?.add) {
                    notification.add(
                        _t("Tarifa cambiada a Efectivo: %s", cashPl.name),
                        { type: "info" }
                    );
                }
            }
        } else {
            // Cambiar a lista con tarjeta (+2%)
            const basePl = order.base_cash_pricelist_id || order.pricelist_id || this.pos?.config?.pricelist_id;
            if (!order.base_cash_pricelist_id && basePl) {
                order.base_cash_pricelist_id = basePl;
            }
            const cardPl = findCardPricelist(this.pos, basePl);
            if (cardPl) {
                order.setPricelist(cardPl);
                if (notification?.add) {
                    notification.add(
                        _t("Tarifa cambiada a Tarjeta (+2%): %s", cardPl.name),
                        { type: "warning" }
                    );
                }
            } else {
                if (notification?.add) {
                    notification.add(
                        _t("No se encontró una tarifa espejo 2.0 / Especial TD para la lista activa."),
                        { type: "danger" }
                    );
                }
            }
        }
    },
});
