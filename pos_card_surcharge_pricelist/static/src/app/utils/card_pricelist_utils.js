export function isCardPaymentMethod(paymentMethod) {
    if (!paymentMethod) return false;
    if (paymentMethod.apply_card_surcharge) return true;
    const name = (paymentMethod.name || "").toLowerCase();
    if (name.includes("efectivo") || name.includes("transferencia") || name.includes("vales") || name.includes("cliente")) {
        return false;
    }
    return name.includes("tarjeta") || name.includes("tpv") || name.includes("mifel");
}

export function findCardPricelist(pos, currentPricelist, paymentMethod = null) {
    // 1. Prioridad Máxima: Tarifa configurada específicamente en el método de pago
    if (paymentMethod && paymentMethod.card_pricelist_id) {
        const pmPlId = paymentMethod.card_pricelist_id.id || paymentMethod.card_pricelist_id;
        const pmPl = pos.models["product.pricelist"]?.get ? pos.models["product.pricelist"].get(pmPlId) : null;
        if (pmPl) return pmPl;
    }

    if (!currentPricelist) return null;
    const name = currentPricelist.name || "";
    if (currentPricelist.is_special_td || name.includes("2.0")) {
        return currentPricelist; // Ya es lista con tarjeta / especial TD
    }

    const allPricelists = pos.models["product.pricelist"]?.getAll ? 
        pos.models["product.pricelist"].getAll() : 
        (pos.models["product.pricelist"] || []);

    const suffix = pos.config.card_pricelist_suffix || "2.0";
    const target1 = `${name} ${suffix}`.trim().toLowerCase();
    const target2 = `${name} 2.0`.trim().toLowerCase();
    const target3 = `${name}.2.0`.trim().toLowerCase();

    // 2. Coincidencia exacta con lista marcada como is_special_td
    for (const pl of allPricelists) {
        if (pl.is_special_td) {
            const plName = (pl.name || "").trim().toLowerCase();
            if (plName === target1 || plName === target2 || plName === target3) {
                return pl;
            }
        }
    }

    // 3. Coincidencia exacta por sufijo de nombre
    for (const pl of allPricelists) {
        const plName = (pl.name || "").trim().toLowerCase();
        if (plName === target1 || plName === target2 || plName === target3) {
            return pl;
        }
    }

    // 4. Coincidencia parcial con is_special_td que contenga el nombre base
    for (const pl of allPricelists) {
        if (pl.is_special_td) {
            const plName = (pl.name || "").trim().toLowerCase();
            if (plName.includes(name.trim().toLowerCase())) {
                return pl;
            }
        }
    }

    // 5. Coincidencia parcial que incluya el nombre base y "2.0"
    for (const pl of allPricelists) {
        const plName = (pl.name || "").trim().toLowerCase();
        if (plName.includes(name.trim().toLowerCase()) && plName.includes("2.0")) {
            return pl;
        }
    }

    // 6. Fallback: Lista configurada por caja / compañía (default_card_pricelist_id)
    if (pos.config.default_card_pricelist_id) {
        const defaultId = pos.config.default_card_pricelist_id.id || pos.config.default_card_pricelist_id;
        const defaultPl = pos.models["product.pricelist"]?.get ? pos.models["product.pricelist"].get(defaultId) : null;
        if (defaultPl) return defaultPl;
    }

    return null;
}
