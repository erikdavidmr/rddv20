function getPricelistId(val) {
    if (!val) return null;
    if (typeof val === "number") return val;
    if (Array.isArray(val) && val.length > 0) return val[0];
    if (typeof val === "object" && val.id) return val.id;
    return null;
}

function cleanName(n) {
    return (n || "").replace(/\s*\([A-Z]{3}\)\s*$/i, "").trim().toLowerCase();
}

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
    const getPlById = (id) => {
        if (!id) return null;
        if (pos.models?.["product.pricelist"]?.get) {
            const pl = pos.models["product.pricelist"].get(id);
            if (pl) return pl;
        }
        if (pos.config?.available_pricelist_ids) {
            const pl = pos.config.available_pricelist_ids.find((p) => p.id === id);
            if (pl) return pl;
        }
        return null;
    };

    // 1. Prioridad Máxima: Tarifa configurada específicamente en el método de pago
    if (paymentMethod && paymentMethod.card_pricelist_id) {
        const pmPlId = getPricelistId(paymentMethod.card_pricelist_id);
        const pmPl = getPlById(pmPlId);
        if (pmPl) return pmPl;
    }

    if (!currentPricelist) return null;
    const baseClean = cleanName(currentPricelist.name || currentPricelist.display_name);

    if (currentPricelist.is_special_td || baseClean.includes("2.0")) {
        return currentPricelist; // Ya es lista con tarjeta / especial TD
    }

    // Unir todas las fuentes de listas de precios disponibles en el TPV
    const plMap = new Map();
    if (pos.models?.["product.pricelist"]?.getAll) {
        for (const pl of pos.models["product.pricelist"].getAll()) {
            if (pl && pl.id) plMap.set(pl.id, pl);
        }
    }
    if (pos.config?.available_pricelist_ids) {
        for (const pl of pos.config.available_pricelist_ids) {
            if (pl && pl.id) plMap.set(pl.id, pl);
        }
    }
    const allPricelists = Array.from(plMap.values());

    const suffix = (pos.config?.card_pricelist_suffix || "2.0").trim().toLowerCase();
    const target1 = `${baseClean} ${suffix}`.trim();
    const target2 = `${baseClean} 2.0`.trim();
    const target3 = `${baseClean}.2.0`.trim();

    // 2. Coincidencia exacta con lista marcada como is_special_td
    for (const pl of allPricelists) {
        if (pl.is_special_td) {
            const plClean = cleanName(pl.name || pl.display_name);
            if (plClean === target1 || plClean === target2 || plClean === target3) {
                return pl;
            }
        }
    }

    // 3. Coincidencia exacta por sufijo de nombre
    for (const pl of allPricelists) {
        const plClean = cleanName(pl.name || pl.display_name);
        if (plClean === target1 || plClean === target2 || plClean === target3) {
            return pl;
        }
    }

    // 4. Coincidencia parcial con is_special_td que contenga el nombre base y sufijo
    for (const pl of allPricelists) {
        if (pl.is_special_td) {
            const plClean = cleanName(pl.name || pl.display_name);
            if (plClean.includes(baseClean) && (plClean.includes("2.0") || plClean.includes(suffix))) {
                return pl;
            }
        }
    }

    // 5. Coincidencia parcial general con nombre base y 2.0
    for (const pl of allPricelists) {
        const plClean = cleanName(pl.name || pl.display_name);
        if (plClean.includes(baseClean) && plClean.includes("2.0")) {
            return pl;
        }
    }

    // 6. Fallback a configuración de la caja o compañía (default_card_pricelist_id)
    if (pos.config?.default_card_pricelist_id) {
        const defaultId = getPricelistId(pos.config.default_card_pricelist_id);
        const defaultPl = getPlById(defaultId);
        if (defaultPl) return defaultPl;
    }

    // 7. Cualquier lista disponible en el TPV marcada como is_special_td
    for (const pl of allPricelists) {
        if (pl.is_special_td) {
            return pl;
        }
    }

    return null;
}
