/*@odoo-module */
/* global Sha1 */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { PosAccessRightPlugin } from "@point_of_sale/app/plugins/access_right_plugin";
import { Component, proxy, useProps, t, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

patch(PosAccessRightPlugin.prototype, {
    get canCloseSession() {
        if (this.config.module_pos_hr && this.config.enable_restriction_on_session_close) {
            return this.hasEmployeeRole(["cashier", "manager"]);
        }
        return super.canCloseSession;
    },
});

export class ManagerSelectPopup extends Component {
    static template = xml`
        <div class="popup p-3">
            <div class="header mb-3 border-bottom pb-2">
                <h4 class="mb-0 text-primary"><i class="fa fa-lock me-2"/> <t t-esc="this.props.title"/></h4>
            </div>
            <div class="body">
                <!-- Resumen de Arqueo para Transparencia Total -->
                <div class="card mb-3 bg-light border-0 shadow-sm">
                    <div class="card-body p-3">
                        <div class="row text-center">
                            <div class="col-4 border-end">
                                <small class="text-muted d-block">Esperado</small>
                                <span class="fw-bold fs-6 text-dark"><t t-esc="this.cashExpected"/></span>
                            </div>
                            <div class="col-4 border-end">
                                <small class="text-muted d-block">Contado</small>
                                <span class="fw-bold fs-6 text-dark"><t t-esc="this.cashCounted"/></span>
                            </div>
                            <div class="col-4">
                                <small class="text-muted d-block">Diferencia</small>
                                <span t-att-class="this.diffClass" class="fw-bold fs-6">
                                    <t t-esc="this.diffText"/>
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="mb-3 text-center">
                    <label class="form-label fw-bold text-secondary mb-1">
                        Ingrese PIN de Gerente o Código Temporal OTP:
                    </label>
                    <input type="password" 
                           t-model.proxy="this.state.pin" 
                           class="form-control form-control-lg text-center fs-4 fw-bold letter-spacing-lg" 
                           placeholder="••••" 
                           autofocus="1" 
                           t-on-keyup="this._onPinKeyup"/>
                    <small class="text-muted d-block mt-1">
                        Si el gerente no está en la sucursal, solicite un código temporal remoto.
                    </small>
                </div>
            </div>

            <div class="footer d-flex justify-content-between align-items-center flex-wrap gap-2 pt-2 border-top">
                <div class="d-flex gap-2">
                    <button t-on-click="this.confirm" class="btn btn-primary px-3">
                        <i class="fa fa-key me-1"/> Confirmar Cierre
                    </button>
                    <button t-on-click="this.requestRemoteOtp" class="btn btn-info text-white px-3">
                        <i class="fa fa-paper-plane me-1"/> Solicitar Código Remoto
                    </button>
                </div>
                <button t-on-click="this.cancel" class="btn btn-secondary px-3">
                    Cancelar
                </button>
            </div>
        </div>`;

    props = useProps({
        title: t.string().optional(""),
        managers: t.array(),
        sessionData: t.object().optional({}),
        onConfirm: t.function(),
    });

    setup() {
        this.state = proxy({
            pin: "",
        });
    }

    get cashExpected() {
        return this.env.utils.formatCurrency(this.props.sessionData?.cashData?.expected || 0);
    }

    get cashCounted() {
        return this.env.utils.formatCurrency(this.props.sessionData?.cashData?.counted || 0);
    }

    get diffClass() {
        const diff = this.props.sessionData?.cashData?.difference || 0;
        if (diff === 0) return "text-success";
        return diff > 0 ? "text-warning" : "text-danger";
    }

    get diffText() {
        const diff = this.props.sessionData?.cashData?.difference || 0;
        return this.env.utils.formatCurrency(diff);
    }

    _onPinKeyup(ev) {
        if (ev.key === 'Enter') {
            this.confirm();
        }
    }

    _formatClosingDetails() {
        const cashExpected = this.cashExpected;
        const cashCounted = this.cashCounted;
        const diff = this.props.sessionData?.cashData?.difference || 0;
        const diffFormatted = this.diffText;
        const diffDesc = diff === 0 ? "Sin diferencias ($0.00)" : (diff > 0 ? `SOBRANTE: +${diffFormatted}` : `⚠️ FALTANTE: ${diffFormatted}`);
        const totalOrders = this.props.sessionData?.salesData?.totalOrders || 0;
        const totalSales = this.env.utils.formatCurrency(this.props.sessionData?.salesData?.totalAmount || 0);
        const notes = this.props.sessionData?.closingNotes ? ` | Notas: ${this.props.sessionData.closingNotes}` : "";

        return _t("Cierre de Caja - Esperado: %s | Contado: %s | %s | Ventas: %s (%s pedidos)%s",
            cashExpected, cashCounted, diffDesc, totalSales, totalOrders, notes);
    }

    async requestRemoteOtp() {
        try {
            const pos = this.env.services.pos;
            const details = this._formatClosingDetails();

            const otpRes = await this.env.services.orm.call("pos.approval.otp", "action_request_otp", [{
                config_id: pos.config.id,
                session_id: pos.config.current_session_id?.id,
                cashier_id: pos.accessRight.cashier?.id,
                action_type: 'session_close',
                details: details,
                receipt_number: '',
                order_number: '',
            }]);

            if (otpRes && otpRes.success) {
                await this.env.services.dialog.add(AlertDialog, {
                    title: _t("Código Temporal Enviado"),
                    body: _t("Se ha enviado un código de autorización con el resumen del corte al correo: %s.\nVigencia: %s minutos. Solicite el código al gerente e ingréselo a continuación.", otpRes.email, otpRes.validity_minutes),
                });
            } else {
                await this.showError("Error al Solicitar Código", otpRes?.message || _t("No fue posible generar el código temporal."));
            }
        } catch (err) {
            await this.showError("Error de Conexión", err.message || err);
        }
    }

    async confirm() {
        if (!this.state.pin) {
            await this.showError("PIN Requerido", "Por favor ingrese el PIN o Código Temporal.");
            return;
        }

        const hashedPin = Sha1.hash(this.state.pin);

        // 1. Reconocimiento automático de gerente presencial (sin selector desplegable)
        const matchedManager = this.props.managers.find(
            m => m._pin && m._pin === hashedPin
        );

        if (matchedManager) {
            this.props.onConfirm({ 
                confirmed: true,
                manager: matchedManager,
                enteredPin: this.state.pin,
                is_otp: false
            });
            return;
        }

        // 2. Si no es el PIN físico de ningún gerente local, validar si es código OTP temporal en backend
        try {
            const pos = this.env.services.pos;
            const details = this._formatClosingDetails();
            const validation = await this.env.services.orm.call("pos.approval.otp", "validate_approval", [
                pos.config.id,
                pos.config.current_session_id?.id,
                this.state.pin,
                'session_close',
                details,
                pos.accessRight.cashier?.id,
            ]);

            if (validation && validation.approved) {
                this.props.onConfirm({
                    confirmed: true,
                    manager: { id: validation.manager_id, name: validation.manager_name },
                    enteredPin: this.state.pin,
                    is_otp: true
                });
                return;
            }
        } catch (err) {
            console.error("[ManagerSelectPopup] Error validando OTP:", err);
        }

        await this.showError("PIN o Código Incorrecto", "El PIN o Código Temporal ingresado no coincide con ningún gerente autorizado ni es válido.");
    }

    cancel() {
        this.props.onConfirm({ confirmed: false });
    }

    async showError(title, body) {
        await this.env.services.dialog.add(AlertDialog, {
            title: _t(title),
            body: _t(body),
        });
    }
}

export class ManagerSelectDialog extends Component {
    static template = xml`
        <Dialog title="this.props.title" size="'md'">
            <ManagerSelectPopup
                title="this.props.title"
                managers="this.props.managers"
                sessionData="this.props.sessionData"
                onConfirm="this.props.onClose" 
            />
        </Dialog>`;
    
    static components = { Dialog, ManagerSelectPopup };
    props = useProps({
        title: t.string(),
        managers: t.array(),
        sessionData: t.object().optional({}),
        onClose: t.function(),
        close: t.function().optional(),
    });
}

// Patch del ClosePosPopup para interceptar el botón "Close Register"
patch(ClosePosPopup.prototype, {
    async confirm() {
        console.log("[ClosePosPopup] Interceptando confirm() - botón Close Register presionado");
        
        // Si no está habilitado pos_hr o la restricción de cierre, proceder directo con el cierre nativo
        if (!this.pos.config.module_pos_hr || !this.pos.config.enable_restriction_on_session_close) {
            return super.confirm(...arguments);
        }

        // Obtener datos de la sesión actual (arqueo, ventas, notas)
        const sessionData = this.getSessionDataForTemplate();
        
        // Mostrar el diálogo de validación de gerente con los datos de arqueo
        const managerValidationResult = await this.showManagerValidation(sessionData);

        if (managerValidationResult?.confirmed) {
            console.log("[ClosePosPopup] Gerente validado, procediendo al cierre");

            // Registrar aprobación en backend si no fue por OTP (el OTP ya se registra solo)
            const approvalRegistered = await this.registerManagerApproval(managerValidationResult);
            if (!approvalRegistered) {
                return;
            }

            return this.closeSession();
        } else {
            console.log("[ClosePosPopup] Validación de gerente cancelada");
            return;
        }
    },

    getSessionDataForTemplate() {
        const cashData = {
            expected: this.props.default_cash_details?.amount || 0,
            counted: parseFloat(this.state.payments[this.props.default_cash_details?.id]?.counted || 0),
            difference: 0
        };
        cashData.difference = cashData.counted - cashData.expected;
        
        const salesData = {
            totalOrders: this.props.orders_details?.quantity || 0,
            totalAmount: this.props.orders_details?.amount || 0
        };
        
        const closingNotes = this.state.notes || '';
        const sessionStart = this.pos.config.current_session_id?.start_at || 'Unknown';
        
        return {
            cashData,
            salesData,
            closingNotes,
            sessionStart
        };
    },

    async showManagerValidation(sessionData) {
        if (!this.pos.config.module_pos_hr || !this.pos.config.enable_restriction_on_session_close) {
            return { confirmed: true };
        }

        const employeeModel = this.pos.models["hr.employee"];
        if (!employeeModel) {
            return { confirmed: true };
        }

        // Obtener lista de managers autorizados en este POS
        const managers = this.pos.models["hr.employee"].getAll().filter(
            (employee) => employee._role === "manager"
        );

        if (!managers.length) {
            return { confirmed: true };
        }

        return new Promise((resolve) => {
            const dialogProps = {
                title: _t("Autorización de Cierre de Caja"),
                managers: managers,
                sessionData: sessionData,
                onClose: (result) => {
                    resolve(result);
                }
            };
            
            this.dialog.add(ManagerSelectDialog, dialogProps);
        });
    },

    async registerManagerApproval(managerValidationResult) {
        if (this.pos.config.module_pos_hr) {
            const cashier = this.pos.accessRight.cashier;
            if (!cashier?.id) {
                this.dialog.add(AlertDialog, {
                    title: _t("Cajero no disponible"),
                    body: _t("No se pudo identificar al cajero para registrar la aprobación."),
                });
                return false;
            }

            // Si fue validado por OTP remoto, el backend ya lo registró en manager.approval
            if (managerValidationResult.is_otp) {
                return true;
            }

            try {
                await this.env.services.orm.call(
                    "manager.approval",
                    "getting_all_data",
                    [{
                        session_id: this.pos.config.current_session_id.id, 
                        manager: managerValidationResult.manager.id, 
                        cashier1: cashier.id,
                        state: 'session_close',
                        is_otp: false
                    }]
                );
                return true;
            } catch (error) {
                console.error("[ClosePosPopup] Error registrando aprobación:", error);
                this.dialog.add(AlertDialog, {
                    title: _t("Error al registrar aprobación"),
                    body: _t("La sesión no se pudo cerrar porque falló el registro de aprobación."),
                });
                return false;
            }
        }
        return true;
    }
});
