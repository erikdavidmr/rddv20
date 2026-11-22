export function isCardPaymentMethod(paymentMethod) {
    if (!paymentMethod) return false;
    if (paymentMethod.apply_card_surcharge) return true;
    const name = (paymentMethod.name || "").toLowerCase();
    return name.includes("tarjeta") || name.includes("tpv") || name.includes("mifel") || name.includes("terminal");
}

export function findCardPricelist(pos, currentPricelist) {
    if (!currentPricelist) return null;
    const name = currentPricelist.name || "";
    if (name.includes("2.0")) {
        return currentPricelist; // Ya es lista con tarjeta
    }

    const suffix = pos.config.card_pricelist_suffix || "2.0";
    const allPricelists = pos.models["product.pricelist"]?.getAll ? 
        pos.models["product.pricelist"].getAll() : 
        (pos.models["product.pricelist"] || []);

    const target1 = `${name} ${suffix}`.trim().toLowerCase();
    const target2 = `${name} 2.0`.trim().toLowerCase();
    const target3 = `${name}.2.0`.trim().toLowerCase();

    // 1. Coincidencia exacta con sufijo
    for (const pl of allPricelists) {
        const plName = (pl.name || "").trim().toLowerCase();
        if (plName === target1 || plName === target2 || plName === target3) {
            return pl;
        }
    }

    // 2. Coincidencia parcial que incluya el nombre base y "2.0"
    for (const pl of allPricelists) {
        const plName = (pl.name || "").trim().toLowerCase();
        if (plName.includes(name.trim().toLowerCase()) && plName.includes("2.0")) {
            return pl;
        }
    }

    // 3. Fallback: default_card_pricelist_id
    if (pos.config.default_card_pricelist_id) {
        const defaultId = pos.config.default_card_pricelist_id.id || pos.config.default_card_pricelist_id;
        const defaultPl = pos.models["product.pricelist"].get(defaultId);
        if (defaultPl) return defaultPl;
    }

    return null;
}
