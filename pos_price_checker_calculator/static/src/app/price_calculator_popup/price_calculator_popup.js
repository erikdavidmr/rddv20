import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";

export class PriceCalculatorPopup extends Component {
    static template = "pos_price_checker_calculator.PriceCalculatorPopup";
    static components = { Dialog };

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.searchInputRef = useRef("searchInput");
        this.moneyInputRef = useRef("moneyInput");
        this.qtyInputRef = useRef("qtyInput");

        this.state = useState({
            searchQuery: "",
            isSearching: false,
            searchResults: [],
            selectedProduct: null,
            inputMoney: "",
            inputQty: "",
            calculatedMoney: 0,
            calculatedQty: 0,
            piecesFit: 0,
            leftoverMoney: 0,
        });

        this.searchTimeout = null;

        useHotkey("escape", () => this.cancel());
        useHotkey("enter", () => this.onEnterPress());

        onMounted(() => {
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }
        });
    }

    cancel() {
        this.props.close();
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        clearTimeout(this.searchTimeout);

        if (!this.state.searchQuery.trim()) {
            this.state.searchResults = [];
            return;
        }

        this.searchTimeout = setTimeout(() => {
            this.performSearch();
        }, 250);
    }

    async onSearchKeyDown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            if (this.state.searchResults.length > 0) {
                this.selectProduct(this.state.searchResults[0]);
            } else if (this.state.searchQuery.trim()) {
                await this.performSearch(true);
            }
        }
    }

    async performSearch(autoSelectFirst = false) {
        const query = this.state.searchQuery.trim();
        if (!query) return;

        this.state.isSearching = true;
        try {
            const order = this.pos.getOrder();
            const pricelistId = order?.pricelist_id?.id || false;

            const results = await this.orm.call(
                "product.product",
                "search_price_calculator_products",
                [],
                {
                    query: query,
                    pricelist_id: pricelistId,
                    limit: 12,
                }
            );

            this.state.searchResults = results || [];

            if (autoSelectFirst && this.state.searchResults.length > 0) {
                this.selectProduct(this.state.searchResults[0]);
            } else if (this.state.searchResults.length === 1 && query.length >= 4) {
                this.selectProduct(this.state.searchResults[0]);
            }
        } catch (error) {
            console.error("Error searching products for calculator:", error);
        } finally {
            this.state.isSearching = false;
        }
    }

    selectProduct(product) {
        this.state.selectedProduct = product;
        this.state.searchResults = [];

        if (product.is_weight) {
            // Producto a granel: default 1 kg
            this.state.inputQty = "1.000";
            this.state.calculatedQty = 1.0;
            this.state.calculatedMoney = product.price_incl;
            this.state.inputMoney = product.price_incl.toFixed(2);
        } else {
            // Empaque / Unidad: default 1 pieza
            this.state.inputQty = "1";
            this.state.calculatedQty = 1;
            this.state.calculatedMoney = product.price_incl;
            this.state.inputMoney = product.price_incl.toFixed(2);
            this.state.piecesFit = 1;
            this.state.leftoverMoney = 0;
        }

        // Auto enfocar el campo de dinero para cálculo rápido
        setTimeout(() => {
            if (this.moneyInputRef.el) {
                this.moneyInputRef.el.focus();
                this.moneyInputRef.el.select();
            }
        }, 100);
    }

    async onSelectSibling(sibling) {
        try {
            const order = this.pos.getOrder();
            const pricelistId = order?.pricelist_id?.id || false;
            const fullSibling = await this.orm.call(
                "product.product",
                "get_price_calculator_product_by_id",
                [sibling.id],
                { pricelist_id: pricelistId }
            );
            if (fullSibling) {
                this.selectProduct(fullSibling);
            }
        } catch (err) {
            console.error("Error loading sibling product:", err);
        }
    }

    clearSelectedProduct() {
        this.state.selectedProduct = null;
        this.state.searchQuery = "";
        this.state.searchResults = [];
        this.state.inputMoney = "";
        this.state.inputQty = "";
        this.state.calculatedMoney = 0;
        this.state.calculatedQty = 0;
        this.state.piecesFit = 0;
        this.state.leftoverMoney = 0;

        setTimeout(() => {
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }
        }, 100);
    }

    onMoneyInput(ev) {
        const money = parseFloat(ev.target.value) || 0;
        this.state.inputMoney = ev.target.value;

        if (!this.state.selectedProduct || this.state.selectedProduct.price_incl <= 0) {
            return;
        }

        const unitPrice = this.state.selectedProduct.price_incl;

        if (this.state.selectedProduct.is_weight) {
            // Peso exacto calculado en Kg (redondeado a 3 decimales / gramos)
            const kg = Math.round((money / unitPrice) * 1000) / 1000;
            this.state.calculatedQty = kg;
            this.state.inputQty = kg > 0 ? kg.toFixed(3) : "";
            this.state.calculatedMoney = Math.round(kg * unitPrice * 100) / 100;
        } else {
            // Empaque / Pieza: calcular cuántas piezas caben
            const pieces = Math.floor(money / unitPrice);
            const total = Math.round(pieces * unitPrice * 100) / 100;
            const leftover = Math.round((money - total) * 100) / 100;

            this.state.piecesFit = pieces;
            this.state.leftoverMoney = leftover;
            this.state.calculatedQty = pieces;
            this.state.inputQty = pieces > 0 ? pieces.toString() : "";
            this.state.calculatedMoney = total;
        }
    }

    onQtyInput(ev) {
        const qty = parseFloat(ev.target.value) || 0;
        this.state.inputQty = ev.target.value;

        if (!this.state.selectedProduct || this.state.selectedProduct.price_incl <= 0) {
            return;
        }

        const unitPrice = this.state.selectedProduct.price_incl;
        const total = Math.round(qty * unitPrice * 100) / 100;

        this.state.calculatedQty = qty;
        this.state.calculatedMoney = total;
        this.state.inputMoney = total > 0 ? total.toFixed(2) : "";

        if (!this.state.selectedProduct.is_weight) {
            this.state.piecesFit = Math.floor(qty);
            this.state.leftoverMoney = 0;
        }
    }

    setQuickWeight(grams) {
        const qtyKg = grams / 1000.0;
        const unitPrice = this.state.selectedProduct.price_incl;
        const total = Math.round(qtyKg * unitPrice * 100) / 100;

        this.state.inputQty = qtyKg.toFixed(3);
        this.state.calculatedQty = qtyKg;
        this.state.inputMoney = total.toFixed(2);
        this.state.calculatedMoney = total;
    }

    onEnterPress() {
        if (this.state.selectedProduct && this.state.calculatedQty > 0) {
            this.addToOrder();
        }
    }

    async addToOrder() {
        const prod = this.state.selectedProduct;
        const qty = this.state.calculatedQty;

        if (!prod || qty <= 0) {
            return;
        }

        let posProduct = this.pos.models["product.product"].get(prod.id);
        if (!posProduct) {
            // Si el producto no estaba precargado en la sesión activa de la caja
            await this.pos.loadNewProducts([["id", "=", prod.id]], 0, 1);
            posProduct = this.pos.models["product.product"].get(prod.id);
        }

        if (posProduct) {
            await this.pos.addLineToCurrentOrder(
                {
                    product_id: posProduct,
                    product_tmpl_id: posProduct.product_tmpl_id,
                    qty: qty,
                },
                {},
                false // configure = false para que no abra báscula ya que la cantidad viene calculada
            );

            this.notification.add(
                _t("Agregado al ticket: %s x %s ($%s)", qty, posProduct.display_name, this.state.calculatedMoney.toFixed(2)),
                { type: "success" }
            );
            this.props.close();
        } else {
            this.notification.add(
                _t("No se pudo cargar el producto en el ticket actual."),
                { type: "danger" }
            );
        }
    }

    formatCurrency(amount) {
        return this.pos.formatCurrency(amount || 0);
    }
}
