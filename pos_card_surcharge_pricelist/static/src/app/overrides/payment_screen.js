import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { _t } from "@web/core/l10n/translation";
import { isCardPaymentMethod, findCardPricelist } from "@pos_card_surcharge_pricelist/app/utils/card_pricelist_utils";

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod, args = {}) {
        const isCard = isCardPaymentMethod(paymentMethod);

        if (this.pos?.config?.enable_card_surcharge && isCard) {
            const currentOrder = this.currentOrder;
            if (currentOrder) {
                const basePl = currentOrder.base_cash_pricelist_id || currentOrder.pricelist_id || this.pos?.config?.pricelist_id;
                if (!currentOrder.base_cash_pricelist_id && basePl) {
                    currentOrder.base_cash_pricelist_id = basePl;
                }

                const cardPricelist = findCardPricelist(
                    this.pos,
                    basePl,
                    paymentMethod
                );
                if (cardPricelist && currentOrder.pricelist_id?.id !== cardPricelist.id) {
                    currentOrder.setPricelist(cardPricelist);
                    const notification = this.notification || this.pos?.notification;
                    if (notification?.add) {
                        notification.add(
                            _t("Tarifa con tarjeta (+2%) aplicada: %s", cardPricelist.name),
                            { type: "info" }
                        );
                    }
                }
            }
        }

        return super.addNewPaymentLine(...arguments);
    },

    deletePaymentLine(uuid) {
        super.deletePaymentLine(...arguments);

        if (this.pos?.config?.enable_card_surcharge && this.currentOrder?.base_cash_pricelist_id) {
            const hasCardPayment = this.paymentLines?.some?.((line) => {
                return isCardPaymentMethod(line.payment_method_id);
            });

            if (!hasCardPayment && this.currentOrder.pricelist_id?.id !== this.currentOrder.base_cash_pricelist_id.id) {
                const cashPricelist = this.currentOrder.base_cash_pricelist_id;
                this.currentOrder.setPricelist(cashPricelist);
                const notification = this.notification || this.pos?.notification;
                if (notification?.add) {
                    notification.add(
                        _t("Tarifa de efectivo restaurada: %s", cashPricelist.name),
                        { type: "info" }
                    );
                }
            }
        }
    },
});
