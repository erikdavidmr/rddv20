/** @odoo-module 

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { reactive } from "@odoo/owl";

patch(ProductScreen.prototype, {
    
    
    async addProductToOrder(product) {
        // === LÓGICA ANTES DE AGREGAR EL PRODUCTO ===
        console.log("Agregando producto:", product.display_name);
        
        // Ejemplo: Validar stock antes de agregar
        if (this.pos.config.limit_product_qty && product.qty_available <= 0) {
          
            return;
        }
        
        // Ejemplo: Validar precio
        if (product.list_price <= 0) {
          
            return;
        }
        
        // Ejemplo: Validar límite de cantidad por producto
        const currentQty = this.state.quantityByProductTmplId[product.product_tmpl_id] || 0;
        const maxQty = 10; // Límite ejemplo
        if (currentQty >= maxQty) {
           
            return;
        }

        try {
            // === LLAMAR AL MÉTODO ORIGINAL ===
            await reactive(this.pos).addLineToCurrentOrder({ product_id: product }, {});
            
            // === LÓGICA DESPUÉS DE AGREGAR EL PRODUCTO ===
            
            // Ejemplo: Mostrar notificación de éxito
         
            
            // Ejemplo: Aplicar descuento automático si es producto especial
            if (product.categ_id?.name === "Ofertas") {
                const orderLine = this.currentOrder.get_last_orderline();
                if (orderLine && orderLine.product_id.id === product.id) {
                    this.pos.setDiscountFromUI(orderLine, 10); // 10% descuento
                    
                }
            }
            
            // Ejemplo: Agregar producto relacionado automáticamente
            if (product.default_code === "COMBO001") {
                const relatedProduct = this.pos.models["product.product"].getBy("default_code", "BEBIDA001");
                if (relatedProduct) {
                    await reactive(this.pos).addLineToCurrentOrder({ product_id: relatedProduct }, {});
                 
                }
            }
            
            // Ejemplo: Log para auditoría
            console.log(`Producto agregado - ID: ${product.id}, Cantidad total en orden: ${this.currentOrder.totalQuantity}`);
            
        } catch (error) {
            console.error("Error al agregar producto:", error);
            
        }
    },
    
    _validateProductBeforeAdd(product) {
        // Validaciones personalizadas
        const validations = [
            {
                condition: !product.available_in_pos,
                message: "Producto no disponible en POS"
            },
            {
                condition: !product.sale_ok,
                message: "Producto no disponible para venta"
            },
            {
                condition: product.list_price <= 0,
                message: "Producto sin precio configurado"
            }
        ];
        
        for (const validation of validations) {
            if (validation.condition) {
               
                return false;
            }
        }
        
        return true;
    }
});**/