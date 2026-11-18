/*@odoo-module */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { Component, useState, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class ManagerSelectPopup extends Component {
    static template = xml`
        <div class="popup">
            <div class="header">
                <t t-esc="props.title"/>
            </div>
            <div class="body">
                <select t-model="state.selectedManagerId" class="form-select mb-3">
                    <t t-foreach="props.managers" t-as="manager" t-key="manager.id">
                        <option t-att-value="manager.id" t-esc="manager.name"/>
                    </t>
                </select>
                <input type="password" t-model="state.pin" class="form-control mb-3" placeholder="Enter PIN" t-on-keyup="_onPinKeyup"/>
            </div>
            <div class="footer">
                <button t-on-click="confirm" class="btn btn-primary">Confirm</button>
                <button t-on-click="cancel" class="btn btn-secondary">Cancel</button>
            </div>
        </div>`;

    static props = {
        title: { type: String, optional: true },
        managers: Array,
        onConfirm: Function,
    };

    setup() {
        console.log("[ManagerSelectPopup] Setup iniciado");
        this.state = useState({
            selectedManagerId: this.props.managers[0]?.id || null,
            pin: "",
        });
        console.log("[ManagerSelectPopup] Estado inicial:", this.state);
    }

    _onPinKeyup(ev) {
        if (ev.key === 'Enter') {
            this.confirm();
        }
    }

    async confirm() {
        console.log("[ManagerSelectPopup] Confirm llamado, estado actual:", this.state);
        
        const selectedManager = this.props.managers.find(u => u.id === parseInt(this.state.selectedManagerId, 10));
        console.log("[ManagerSelectPopup] Manager seleccionado:", selectedManager);

        if (!selectedManager) {
            console.error("[ManagerSelectPopup] Error: Manager no encontrado");
            await this.showError("Selection Error", "Manager not found");
            this.props.onConfirm({ confirmed: false, error: "Manager not found" });
            return;
        }
        
        if (!this.state.pin) {
            console.error("[ManagerSelectPopup] Error: PIN no ingresado");
            await this.showError("PIN Required", "Please enter PIN");
            return;
        }
        
        console.log("[ManagerSelectPopup] Validando PIN...");
        if (selectedManager.pin === this.state.pin) {
            console.log("[ManagerSelectPopup] PIN correcto, procediendo");
            this.props.onConfirm({ 
                confirmed: true,
                manager: selectedManager,
                enteredPin: this.state.pin
            });
        } else {
            console.warn("[ManagerSelectPopup] PIN incorrecto");
            await this.showError("Incorrect PIN", "The PIN entered is not valid.");
        }
    }

    cancel() {
        console.log("[ManagerSelectPopup] Cancel llamado");
        this.props.onConfirm({ confirmed: false });
    }

    async showError(title, body) {
        console.log(`[ManagerSelectPopup] Mostrando error: ${title} - ${body}`);
        await this.env.services.dialog.add(AlertDialog, {
            title: _t(title),
            body: _t(body),
        });
    }
}

export class ManagerSelectDialog extends Component {
    static template = xml`
        <Dialog title="props.title" size="'md'">
            <ManagerSelectPopup
                title="props.title"
                managers="props.managers"
                onConfirm="props.onClose" 
            />
        </Dialog>`;
    
    static components = { Dialog, ManagerSelectPopup };
    static props = {
        title: String,
        managers: Array,
        onClose: Function, 
        close: Function, 
        "*": true,
    };
}

// Template genérico que aparece después de hacer clic en "Close Register"
export class SessionCloseTemplatePopup extends Component {
    static template = xml`
        <div class="popup close-session-template">
            <div class="header">
                <h4><t t-esc="props.title"/></h4>
            </div>
            <div class="body">
                <div class="alert alert-info mb-3">
                    <div class="row">
                        <div class="col-md-6">
                            <h6><i class="fa fa-user"></i> Session Information</h6>
                            <p><strong>Manager:</strong> <t t-esc="props.managerName"/></p>
                            <p><strong>Session ID:</strong> <t t-esc="props.sessionId"/></p>
                            <p><strong>Cashier:</strong> <t t-esc="props.cashierName"/></p>
                        </div>
                        <div class="col-md-6">
                            <h6><i class="fa fa-clock-o"></i> Timing</h6>
                            <p><strong>Session Start:</strong> <t t-esc="props.sessionStart"/></p>
                            <p><strong>Close Time:</strong> <t t-esc="props.currentDate"/></p>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card mb-3">
                            <div class="card-header bg-success text-white">
                                <h6 class="mb-0"><i class="fa fa-money"></i> Cash Summary</h6>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-6">
                                        <label class="text-muted">Expected:</label>
                                        <div class="h5 text-success">
                                            <t t-esc="env.utils.formatCurrency(props.cashData.expected || 0)"/>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <label class="text-muted">Counted:</label>
                                        <div class="h5" t-att-class="props.cashData.difference !== 0 ? 'text-warning' : 'text-success'">
                                            <t t-esc="env.utils.formatCurrency(props.cashData.counted || 0)"/>
                                        </div>
                                    </div>
                                </div>
                                <hr class="my-2"/>
                                <div class="row">
                                    <div class="col-12">
                                        <label class="text-muted">Difference:</label>
                                        <div class="h5" t-att-class="props.cashData.difference !== 0 ? 'text-danger' : 'text-success'">
                                            <t t-esc="env.utils.formatCurrency(props.cashData.difference || 0)"/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card mb-3">
                            <div class="card-header bg-primary text-white">
                                <h6 class="mb-0"><i class="fa fa-shopping-cart"></i> Sales Summary</h6>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-6">
                                        <label class="text-muted">Total Orders:</label>
                                        <div class="h5 text-primary">
                                            <t t-esc="props.salesData.totalOrders || 0"/>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <label class="text-muted">Total Amount:</label>
                                        <div class="h5 text-primary">
                                            <t t-esc="env.utils.formatCurrency(props.salesData.totalAmount || 0)"/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Notas de cierre si existen -->
                <div t-if="props.closingNotes" class="card mb-3">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="fa fa-comment"></i> Closing Notes</h6>
                    </div>
                    <div class="card-body">
                        <p class="mb-0" t-esc="props.closingNotes"/>
                    </div>
                </div>
                
                <!-- Sección expandible para futuras funcionalidades -->
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="fa fa-info-circle"></i> Additional Information</h6>
                    </div>
                    <div class="card-body text-muted">
                        <p class="mb-0">This section can be expanded with additional closing procedures, reports, or validations.</p>
                    </div>
                </div>
            </div>
            <div class="footer mt-3">
                <div class="d-flex justify-content-between">
                   
                    <div class="btn-group">
                        <button t-on-click="proceedWithClose" class="btn btn-success">
                            <i class="fa fa-check"></i> Confirm Session Close
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

    static props = {
        title: { type: String, optional: true },
        managerName: String,
        cashierName: String,
        sessionId: [String, Number],
        sessionStart: String,
        currentDate: String,
        cashData: Object,
        salesData: Object,
        closingNotes: { type: String, optional: true },
        onConfirm: Function,
    };

    setup() {
        console.log("[SessionCloseTemplatePopup] Setup iniciado");
        console.log("[SessionCloseTemplatePopup] Props recibidas:", this.props);
    }

    proceedWithClose() {
        console.log("[SessionCloseTemplatePopup] Confirmando cierre de sesión definitivo");
        this.props.onConfirm({ confirmed: true, action: 'proceed' });
    }

    cancel() {
        console.log("[SessionCloseTemplatePopup] Cancelando cierre de sesión");
        this.props.onConfirm({ confirmed: false, action: 'cancel' });
    }
}

export class SessionCloseTemplateDialog extends Component {
    static template = xml`
        <Dialog title="props.title" size="'xl'">
            <SessionCloseTemplatePopup
                title="props.title"
                managerName="props.managerName"
                cashierName="props.cashierName"
                sessionId="props.sessionId"
                sessionStart="props.sessionStart"
                currentDate="props.currentDate"
                cashData="props.cashData"
                salesData="props.salesData"
                closingNotes="props.closingNotes"
                onConfirm="props.onClose" 
            />
        </Dialog>`;
    
    static components = { Dialog, SessionCloseTemplatePopup };
    static props = {
        title: String,
        managerName: String,
        cashierName: String,
        sessionId: [String, Number],
        sessionStart: String,
        currentDate: String,
        cashData: Object,
        salesData: Object,
        closingNotes: { type: String, optional: true },
        onClose: Function, 
        close: Function, 
        "*": true,
    };
}

// Patch del ClosePosPopup para interceptar el clic en "Close Register"
patch(ClosePosPopup.prototype, {
    async confirm() {
        console.log("[ClosePosPopup] Interceptando confirm() - botón Close Register presionado");
        
        // Obtener datos de la sesión actual antes de continuar
        const sessionData = this.getSessionDataForTemplate();
        
        // Mostrar el diálogo de validación de manager
        const managerValidationResult = await this.showManagerValidation();
        
        if (managerValidationResult?.confirmed) {
            console.log("[ClosePosPopup] Manager validado, mostrando template de resumen");
            
            // Mostrar el template de resumen con datos de la sesión
            const templateResult = await this.showSessionCloseTemplate(
                managerValidationResult.manager, 
                sessionData
            );
            
            if (templateResult?.confirmed && templateResult?.action === 'proceed') {
                console.log("[ClosePosPopup] Usuario confirmó desde template, procediendo con cierre nativo");
                
                // Registrar la aprobación del manager en el backend
                await this.registerManagerApproval(managerValidationResult);
                
                // Ejecutar el cierre nativo original
                return await super.confirm(...arguments);
            } else {
                console.log("[ClosePosPopup] Usuario canceló desde template, abortando cierre");
                return;
            }
        } else {
            console.log("[ClosePosPopup] Validación de manager fallida o cancelada");
            return;
        }
    },

    getSessionDataForTemplate() {
        console.log("[ClosePosPopup] Recopilando datos de sesión para template");
        
        // Obtener datos de efectivo
        const cashData = {
            expected: this.props.default_cash_details?.amount || 0,
            counted: parseFloat(this.state.payments[this.props.default_cash_details?.id]?.counted || 0),
            difference: 0
        };
        cashData.difference = cashData.counted - cashData.expected;
        
        // Obtener datos de ventas
        const salesData = {
            totalOrders: this.props.orders_details?.quantity || 0,
            totalAmount: this.props.orders_details?.amount || 0
        };
        
        // Obtener notas de cierre
        const closingNotes = this.state.notes || '';
        
        // Obtener información de sesión
        const sessionStart = this.pos.config.current_session_id?.start_at || 'Unknown';
        
        return {
            cashData,
            salesData,
            closingNotes,
            sessionStart
        };
    },

    async showManagerValidation() {
        console.log("[ClosePosPopup] Iniciando validación de manager");

        // Obtener lista de managers
        const configId = this.pos.config.id;
        const configs = await this.env.services.orm.read("pos.config", [configId], ["advanced_employee_ids"]);
        const configData = configs.length ? configs[0] : null;
        const employee_ids = configData?.advanced_employee_ids || [];
        
        let managers = [];
        if (employee_ids.length) {
            const employees = await this.env.services.orm.read("hr.employee", employee_ids, ["user_id", "pin", "name"]);
            managers = employees
                .filter(e => e.user_id && e.user_id[0]) 
                .map(e => ({
                    id: e.user_id[0], 
                    name: e.user_id[1], 
                    pin: e.pin || "", 
                    employee_name: e.name, 
                }));
        }
        
        console.log("[ClosePosPopup] Managers disponibles:", managers);

        if (!managers.length) {
            console.log("[ClosePosPopup] No hay managers configurados, saltando validación");
            return { confirmed: true, manager: { name: 'System', id: 0 } };
        }

        // Mostrar diálogo de selección de manager
        return new Promise((resolve) => {
            const dialogProps = {
                title: _t("Manager Approval Required for Session Close"),
                managers: managers,
                onClose: (result) => {
                    console.log("[ClosePosPopup] Resultado de validación de manager:", result);
                    resolve(result);
                }
            };
            
            this.dialog.add(ManagerSelectDialog, dialogProps);
        });
    },

    async showSessionCloseTemplate(manager, sessionData) {
        console.log("[ClosePosPopup] Mostrando template de resumen de cierre");
        
        return new Promise((resolve) => {
            const currentDate = new Date().toLocaleString();
            const sessionId = this.pos.config.current_session_id?.id || 'Unknown';
            const cashierName = this.pos.cashier?.name || 'Unknown';
            
            const dialogProps = {
                title: _t("Session Close Confirmation"),
                managerName: manager.name,
                cashierName: cashierName,
                sessionId: sessionId,
                sessionStart: new Date(sessionData.sessionStart).toLocaleString(),
                currentDate: currentDate,
                cashData: sessionData.cashData,
                salesData: sessionData.salesData,
                closingNotes: sessionData.closingNotes,
                onClose: (result) => {
                    console.log("[ClosePosPopup] Resultado de template de cierre:", result);
                    resolve(result);
                }
            };
            
            this.dialog.add(SessionCloseTemplateDialog, dialogProps);
        });
    },

    async registerManagerApproval(managerValidationResult) {
        if (this.pos.config.module_pos_hr) {
            console.log("[ClosePosPopup] Registrando aprobación de manager en backend");
            try {
                await this.env.services.orm.call(
                    "manager.approval",
                    "getting_all_data",
                    [{
                        session_id: this.pos.config.current_session_id.id, 
                        manager: managerValidationResult.manager.id, 
                        cashier1: this.pos.cashier.id, 
                        state: 'session_close'
                    }]
                );
                console.log("[ClosePosPopup] Aprobación registrada exitosamente");
            } catch (error) {
                console.error("[ClosePosPopup] Error al registrar aprobación:", error);
            }
        }
    }
});

/*
static template = xml`
        <div class="popup close-session-template">
            <div class="header">
                <h4><t t-esc="props.title"/></h4>
            </div>
            <div class="body">
                <div class="alert alert-info mb-3">
                    <div class="row">
                        <div class="col-md-6">
                            <h6><i class="fa fa-user"></i> Session Information</h6>
                            <p><strong>Manager:</strong> <t t-esc="props.managerName"/></p>
                            <p><strong>Sesión ID:</strong> <t t-esc="props.sessionId"/></p>
                            <p><strong>Cajero:</strong> <t t-esc="props.cashierName"/></p>
                        </div>
                        <div class="col-md-6">
                            <h6><i class="fa fa-clock-o"></i> Timing</h6>
                            <p><strong>Inicio de sesión:</strong> <t t-esc="props.sessionStart"/></p>
                            <p><strong>Hora de cierre:</strong> <t t-esc="props.currentDate"/></p>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card mb-3">
                            <div class="card-header bg-success text-white">
                                <h6 class="mb-0"><i class="fa fa-money"></i> Resumen de dinero</h6>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-6">
                                        <label class="text-muted">Esperado:</label>
                                        <div class="h5 text-success">
                                            <t t-esc="env.utils.formatCurrency(props.cashData.expected || 0)"/>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <label class="text-muted">Contado:</label>
                                        <div class="h5" t-att-class="props.cashData.difference !== 0 ? 'text-warning' : 'text-success'">
                                            <t t-esc="env.utils.formatCurrency(props.cashData.counted || 0)"/>
                                        </div>
                                    </div>
                                </div>
                                <hr class="my-2"/>
                                <div class="row">
                                    <div class="col-12">
                                        <label class="text-muted">Diferencia:</label>
                                        <div class="h5" t-att-class="props.cashData.difference !== 0 ? 'text-danger' : 'text-success'">
                                            <t t-esc="env.utils.formatCurrency(props.cashData.difference || 0)"/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card mb-3">
                            <div class="card-header bg-primary text-white">
                                <h6 class="mb-0"><i class="fa fa-shopping-cart"></i> Resumen de Ventas</h6>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-6">
                                        <label class="text-muted">Total de Ordenes:</label>
                                        <div class="h5 text-primary">
                                            <t t-esc="props.salesData.totalOrders || 0"/>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <label class="text-muted">Cantidad Ttotal:</label>
                                        <div class="h5 text-primary">
                                            <t t-esc="env.utils.formatCurrency(props.salesData.totalAmount || 0)"/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Notas de cierre si existen -->
                <div t-if="props.closingNotes" class="card mb-3">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="fa fa-comment"></i> Closing Notes</h6>
                    </div>
                    <div class="card-body">
                        <p class="mb-0" t-esc="props.closingNotes"/>
                    </div>
                </div>
                
                <!-- Sección expandible para futuras funcionalidades 
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="fa fa-info-circle"></i> Additional Information</h6>
                    </div>
                    <div class="card-body text-muted">
                        <p class="mb-0">This section can be expanded with additional closing procedures, reports, or validations.</p>
                    </div>
                </div>-->
            </div>
            <div class="footer mt-3">
                <div class="d-flex justify-content-between">
                   
                    <div class="btn-group">
                        <button t-on-click="proceedWithClose" class="btn btn-success">
                            <i class="fa fa-check"></i> Confirmar Cierre de sesión
                        </button>
                    </div>
                </div>
            </div>
        </div>`; */

        /*import { Dialog } from "@web/core/dialog/dialog";
import { SaleDetailsButton } from "@point_of_sale/app/navbar/sale_details_button/sale_details_button";
import { ConfirmationDialog, AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { ConnectionLostError } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { parseFloat } from "@web/views/fields/parsers";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";
import { useAsyncLockedMethod } from "@point_of_sale/app/utils/hooks";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { deduceUrl } from "@point_of_sale/utils";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { PaymentMethodBreakdown } from "@point_of_sale/app/components/payment_method_breakdown/payment_method_breakdown";
import { ClosePosDetailsDialog } from "./close_pos_details_dialog";

export class ClosePosPopup extends Component {
    static components = { SaleDetailsButton, Input, Dialog, PaymentMethodBreakdown };
    static template = "point_of_sale.ClosePosPopup";
    static props = [
        "orders_details",
        "opening_notes",
        "default_cash_details",
        "non_cash_payment_methods",
        "is_manager",
        "amount_authorized_diff",
        "close",
    ];

    setup() {
        this.pos = usePos();
        this.report = useService("report");
        this.hardwareProxy = useService("hardware_proxy");
        this.dialog = useService("dialog");
        this.ui = useState(useService("ui"));
        this.state = useState(this.getInitialState());
        this.confirm = useAsyncLockedMethod(this.confirm);
    }
    autoFillCashCount() {
        const count = this.props.default_cash_details.amount;
        this.state.payments[this.props.default_cash_details.id].counted =
            this.env.utils.formatCurrency(count, false);
        this.setManualCashInput(count);
    }
    get cashMoveData() {
        const { total, moves } = this.props.default_cash_details.moves.reduce(
            (acc, move, i) => {
                acc.total += move.amount;
                acc.moves.push({
                    id: i,
                    name: move.name,
                    amount: move.amount,
                });
                return acc;
            },
            { total: 0, moves: [] }
        );
        return { total, moves };
    }
    async cashMove() {
        await this.pos.cashMove();
        this.dialog.closeAll();
        this.pos.closeSession();
    }
    getInitialState() {
        const initialState = { notes: "", payments: {} };
        if (this.pos.config.cash_control) {
            initialState.payments[this.props.default_cash_details.id] = {
                counted: "0",
            };
        }
        this.props.non_cash_payment_methods.forEach((pm) => {
            if (pm.type === "bank") {
                initialState.payments[pm.id] = {
                    counted: this.env.utils.formatCurrency(pm.amount, false),
                };
            }
        });
        return initialState;
    }
    async confirm() {
        console.group("[CLOSE POPUP] confirm");
        try {
            if (!this.pos.config.cash_control || this.env.utils.floatIsZero(this.getMaxDifference())) {
                console.log("[1] No cash control or zero difference - showing details");
                await this.showClosingDetails();
                return;
            }
            
            if (this.hasUserAuthority()) {
                console.log("[2] User has authority - asking confirmation");
                const response = await ask(this.dialog, {
                    title: _t("Payments Difference"),
                    body: _t("The money counted doesn't match what we expected..."),
                    confirmLabel: _t("Proceed Anyway"),
                    cancelLabel: _t("Discard"),
                });
                
                if (response) {
                    console.log("[3] User confirmed - showing details");
                    await this.showClosingDetails();
                }
                return;
            }
            
            console.log("[4] Showing difference warning");
            this.dialog.add(ConfirmationDialog, {
                title: _t("Payments Difference"),
                body: _t("The maximum difference allowed is %s...", 
                    this.env.utils.formatCurrency(this.props.amount_authorized_diff))
            });
        } finally {
            console.groupEnd();
        }
    }

    async showClosingDetails() {
        console.group("[CLOSE POPUP] showClosingDetails");
        try {
            console.log("[1] Preparing to show dialog");
            
            const result = await new Promise((resolve) => {
                console.log("[2] Creating dialog promise");
                
                const dialogProps = {
                    title: _t("Session Closing Details"),
                    orders_details: this.props.orders_details,
                    opening_notes: this.props.opening_notes,
                    default_cash_details: this.props.default_cash_details,
                    non_cash_payment_methods: this.props.non_cash_payment_methods,
                    is_manager: this.props.is_manager,
                    amount_authorized_diff: this.props.amount_authorized_diff,
                    counted_cash: parseFloat(this.state.payments[this.props.default_cash_details.id].counted),
                };

                console.log("[3] Adding dialog to manager");
                const removeDialog = this.dialog.add(
                    ClosePosDetailsDialog,
                    dialogProps,
                    {
                        onClose: (result) => {
                            console.log("[6] Dialog closed with result:", result);
                            resolve(result?.confirmed || false);
                        },
                    }
                );
                
                console.log("[4] Dialog added successfully");
                this.dialogCloseFn = removeDialog;
            });
            
            console.log("[5] Promise resolved with result:", result);
            return result;
        } catch (error) {
            console.error("[ERROR] in showClosingDetails:", error);
            return false;
        } finally {
            console.groupEnd();
        }
    }

    async cancel() {
        if (this.canCancel()) {
            this.props.close();
        }
    }
    canConfirm() {
        return Object.values(this.state.payments)
            .map((v) => v.counted)
            .every(this.env.utils.isValidFloat);
    }
    async openDetailsPopup() {
        const action = _t("Cash control - closing");
        this.hardwareProxy.openCashbox(action);
        this.dialog.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetails,
            action: action,
            getPayload: (payload) => {
                const { total, moneyDetailsNotes, moneyDetails } = payload;
                this.state.payments[this.props.default_cash_details.id].counted =
                    this.env.utils.formatCurrency(total, false);
                if (moneyDetailsNotes) {
                    this.state.notes = moneyDetailsNotes;
                }
                this.moneyDetails = moneyDetails;
            },
            context: "Closing",
        });
    }
    async downloadSalesReport() {
        return this.report.doAction("point_of_sale.sale_details_report", [this.pos.session.id]);
    }
    setManualCashInput(amount) {
        if (this.env.utils.isValidFloat(amount) && this.moneyDetails) {
            this.state.notes = "";
            this.moneyDetails = null;
        }
    }
    getDifference(paymentId) {
        const counted = this.state.payments[paymentId].counted;
        if (!this.env.utils.isValidFloat(counted)) {
            return NaN;
        }
        const expectedAmount =
            paymentId === this.props.default_cash_details?.id
                ? this.props.default_cash_details.amount
                : this.props.non_cash_payment_methods.find((pm) => pm.id === paymentId).amount;

        return parseFloat(counted) - expectedAmount;
    }

    getMaxDifference() {
        return Math.max(
            ...Object.keys(this.state.payments).map((id) =>
                Math.abs(this.getDifference(parseInt(id)))
            )
        );
    }
    hasUserAuthority() {
        return (
            this.props.is_manager ||
            this.props.amount_authorized_diff == null ||
            this.getMaxDifference() <= this.props.amount_authorized_diff
        );
    }
    canCancel() {
        return true;
    }

    async closeSession() {
        console.log("🚀 [1] closeSession iniciado");
        
        // 1. Forzar diálogo de prueba simple
        const testResult = await this.dialog.add(AlertDialog, {
            title: "TEST",
            body: "¿Este diálogo aparece?",
        });
        console.log("🚀 [2] Resultado diálogo TEST:", testResult);
        
        // 2. Mostrar diálogo de cierre
        console.log("🚀 [3] Mostrando diálogo de cierre");
        const confirmed = await new Promise(resolve => {
            const dialogRef = this.dialog.add(ClosePosDetailsDialog, {
                title: "Diálogo de Cierre",
                onClose: (result) => {
                    console.log("🚀 [4] Diálogo cerrado con:", result);
                    resolve(result?.confirmed || false);
                }
            });
            console.log("🚀 [5] Diálogo añadido:", dialogRef);
        });
        
        console.log("🚀 [6] Confirmación recibida:", confirmed);
        
        if (confirmed) {
            console.log("🚀 [7] Ejecutando cierre real");
            await this._actuallyCloseSession();
        }
    }

    async _actuallyCloseSession() {
        console.group("[CLOSE POPUP] _actuallyCloseSession");
        this.pos._resetConnectedCashier();
        if (this.pos.config.customer_display_type === "proxy") {
            const proxyIP = this.pos.getDisplayDeviceIP();
            fetch(`${deduceUrl(proxyIP)}/hw_proxy/customer_facing_display`, {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ params: { action: "close" } }),
            }).catch(() => {
                console.log("Failed to send data to customer display");
            });
        }
        // If there are orders in the db left unsynced, we try to sync.
        const syncSuccess = await this.pos.push_orders_with_closing_popup();
        if (!syncSuccess) {
            return;
        }
        if (this.pos.config.cash_control) {
            const response = await this.pos.data.call(
                "pos.session",
                "post_closing_cash_details",
                [this.pos.session.id],
                {
                    counted_cash: parseFloat(
                        this.state.payments[this.props.default_cash_details.id].counted
                    ),
                }
            );

            if (!response.successful) {
                return this.handleClosingError(response);
            }
        }

        try {
            await this.pos.data.call("pos.session", "update_closing_control_state_session", [
                this.pos.session.id,
                this.state.notes,
            ]);
        } catch (error) {
            // We have to handle the error manually otherwise the validation check stops the script.
            // In case of "rescue session", we want to display the next popup with "handleClosingError".
            // FIXME
            if (!error.data && error.data.message !== "This session is already closed.") {
                throw error;
            }
        }

        try {
            const bankPaymentMethodDiffPairs = this.props.non_cash_payment_methods
                .filter((pm) => pm.type == "bank")
                .map((pm) => [pm.id, this.getDifference(pm.id)]);
            const response = await this.pos.data.call(
                "pos.session",
                "close_session_from_ui",
                [this.pos.session.id, bankPaymentMethodDiffPairs],
                {
                    context: {
                        login_number: odoo.login_number,
                    },
                }
            );
            if (!response.successful) {
                return this.handleClosingError(response);
            }
            localStorage.removeItem(`pos.session.${odoo.pos_config_id}`);
            location.reload();
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                throw error;
            } else {
                await this.handleClosingControlError();
            }
        }
    }
    async handleClosingControlError() {
        this.dialog.add(
            AlertDialog,
            {
                title: _t("Closing session error"),
                body: _t(
                    "An error has occurred when trying to close the session.\n" +
                        "You will be redirected to the back-end to manually close the session."
                ),
            },
            {
                onClose: () => {
                    this.dialog.add(
                        FormViewDialog,
                        {
                            resModel: "pos.session",
                            resId: this.pos.session.id,
                        },
                        {
                            onClose: async () => {
                                const session = await this.pos.data.read("pos.session", [
                                    this.pos.session.id,
                                ]);
                                if (session[0] && session[0].state === "closed") {
                                    location.reload();
                                } else {
                                    this.pos.redirectToBackend();
                                }
                            },
                        }
                    );
                },
            }
        );
    }
    async handleClosingError(response) {
        this.dialog.add(ConfirmationDialog, {
            title: response.title || "Error",
            body: response.message,
            confirmLabel: _t("Review Orders"),
            cancelLabel: _t("Cancel Orders"),
            confirm: () => {
                if (!response.redirect) {
                    this.props.close();
                    this.pos.showScreen("TicketScreen");
                }
            },
            cancel: async () => {
                if (!response.redirect) {
                    const ordersDraft = this.pos.models["pos.order"].filter((o) => !o.finalized);
                    await this.pos.deleteOrders(ordersDraft, response.open_order_ids);
                    this.closeSession();
                }
            },
            dismiss: async () => {},
        });

        if (response.redirect) {
            window.location.reload();
        }
    }
    getMovesTotalAmount() {
        const amounts = this.props.default_cash_details.moves.map((move) => move.amount);
        return amounts.reduce((acc, x) => acc + x, 0);
    }
}
*/