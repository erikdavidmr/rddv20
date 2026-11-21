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
        confirmText: t.string().optional(_t("Ingresar PIN")),
        cancelText: t.string().optional(_t("Cancelar")),
        requestOtpText: t.string().optional(_t("Solicitar Código Remoto")),
        showRequestOtp: t.boolean().optional(true),
        title: t.string().optional(""),
        description: t.string().optional(""),
        body: t.string().optional(""),
        getPayload: t.function(),
        close: t.function(),
    });

    cancel() {
        this.props.getPayload(false);
        this.props.close();
    }
    confirm() {
        this.props.getPayload('enter_pin');
        this.props.close();
    }
    requestOtp() {
        this.props.getPayload('request_otp');
        this.props.close();
    }
}
