import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { PriceCalculatorPopup } from "@pos_price_checker_calculator/app/price_calculator_popup/price_calculator_popup";

patch(Navbar.prototype, {
    handleKeydown(event) {
        if (event.key === "F4") {
            event.preventDefault();
            this.openPriceCalculator();
            return;
        }
        super.handleKeydown(event);
    },
    openPriceCalculator() {
        this.dialog.add(PriceCalculatorPopup);
    },
});
