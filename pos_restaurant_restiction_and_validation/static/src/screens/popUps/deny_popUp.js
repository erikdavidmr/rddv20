/** @odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useProps, t } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
export class DenyPopup extends Component {
    static template = "pos_restaurant_restiction_and_validation.DenyPopup";
    
    static components = { Dialog };
    
    props = useProps({
        confirmText: t.string().optional(_t("Autorizar")),
        cancelText: t.string().optional(_t("Descartar")),
        title: t.string().optional(""),
        description: t.string().optional(""),
        body: t.string().optional(""),
        getPayload: t.function(),
        close: t.function(),
    });

    cancel(){
        this.props.close();
    }
    confirm() {
        this.props.getPayload(true);
        this.props.close();
    }

}
