/** @odoo-module */

import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { registry } from "@web/core/registry";
import { roundPrecision } from "@web/core/utils/numbers";

export class ProductProductExtended extends ProductProduct {
    /**
     * @override
     */
    setup(vals) {
        // Llamar al setup original primero
        super.setup(vals);
        
        // Acceso seguro a this.raw con verificación
        try {
            if (!this.raw || typeof this.raw !== 'object') {
                console.error('[PUC_ERROR] Invalid raw data for product:', vals?.id);
                return;
            }
            
            // Verificación segura del campo puc_multicompany
            if (!('puc_multicompany' in this.raw)) {
                console.warn('[PUC_WARNING] puc_multicompany not found in product data for product:', this.id);
            } else {
                console.debug('[PUC_DEBUG] puc_multicompany value:', this.raw.puc_multicompany);
            }
        } catch (error) {
            console.error('[PUC_ERROR] Setup verification failed:', error);
        }
    }

    /**
     * @override
     
    getPricelistRule(pricelist, quantity) {
        const rules = !pricelist ? [] : this.cachedPricelistRules[pricelist?.id] || [];
        
        console.log("rules ", rules);
        console.log("rules quantity", quantity);

        const matchingRule = rules.find(rule => quantity < rule.min_quantity);
        
        if (matchingRule) {
            console.log("rule.min_quantity", matchingRule.min_quantity);
            console.log("matchingRule", matchingRule);
        } else {
            console.log("No matching rule found");
        }

        return matchingRule;
    }*/


    /**
     * @override
     */
    get_price(pricelist, quantity, price_extra = 0, quantity2, recurring = false, list_price = false) {
        if (recurring && !pricelist) {
            alert(
                _t(
                    "An error occurred when loading product prices. " +
                        "Make sure all pricelists are available in the POS."
                )
            );
        }
        // Precio base seguro
        
        const basePrice = (list_price || this.lst_price || 0) + (price_extra || 0);
        let price = basePrice;
        const rule = this.getPricelistRule(pricelist, quantity);
        console.log("get rule ", rule);
        console.log("get price ", price);
        console.log("get basePrice ", basePrice);
        quantity2 = quantity2 ? quantity2 : 1;
      
        
        if (rule && rule.base === "standard_price") {
            // Acceso ultra seguro a puc_multicompany
            const pucValue = (this.raw && typeof this.raw === 'object') ? this.raw.puc_multicompany : undefined;
            console.log("get pucValue ", pucValue);
            if (pucValue !== 0) {
                price = parseFloat(pucValue);
                if (!isNaN(price)) {
                    console.debug('[PUC_DEBUG] Using valid puc_multicompany value:', price);
                } else {
                    price = this.standard_price;
                }
            } else {
                price = this.standard_price;
            }
        }
        console.log("get price x2 ", price);
        // Resto de la lógica de cálculo de precio
        if (rule) {
            if (rule.compute_price === "fixed") {
                price = rule.fixed_price;
            } else if (rule.compute_price === "percentage") {
                price = price - price * (rule.percent_price / 100);
            } else {
                
                const price_limit = price;
                price = price*quantity
                console.log("get quantity ", quantity);
                console.log("get quantity2 ", quantity2);
                console.log("get price x3 ", price);
                console.log("get price_discount x3 ", rule.price_discount);
                price -= price * (rule.price_discount / 100);
                price = (price/quantity2)
         
                if (rule.price_round) {
                    price = roundPrecision(price, rule.price_round);
                }
                if (rule.price_surcharge) {
                    price += rule.price_surcharge;
                }
                if (rule.price_min_margin) {
                    price = Math.max(price, price_limit + rule.price_min_margin);
                }
                if (rule.price_max_margin) {
                    price = Math.min(price, price_limit + rule.price_max_margin);
                }
            }
        }
        console.log("get price x4 ", price);
        return price;
            
        
    }
}

// Registro seguro del modelo extendido
try {
    const modelName = ProductProduct.pythonModel;
    const modelRegistry = registry.category("pos_available_models");
    
    // Verificar si el modelo original existe
    if (!modelRegistry.get(modelName)) {
        console.error('[PUC_ERROR] Original ProductProduct model not found in registry');
        throw new Error('Original ProductProduct model not found');
    }
    
    // Eliminar y registrar la nueva implementación
    modelRegistry.remove(modelName);
    modelRegistry.add(modelName, ProductProductExtended);
    console.debug('[PUC_DEBUG] Product model successfully extended');
    
} catch (error) {
    console.error('[PUC_ERROR] Model registration failed:', error);
    // No relanzar el error para evitar bloquear el POS completamente
}