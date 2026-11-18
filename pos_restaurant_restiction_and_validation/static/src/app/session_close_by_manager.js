/*@odoo-module */
/* global Sha1 */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { Component, proxy, useProps, t, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";

export class ManagerSelectPopup extends Component {
    static template = xml`
        <div class="popup">
            <div class="header">
                <t t-esc="this.props.title"/>
            </div>
            <div class="body">
                <select t-model.proxy="this.state.selectedManagerId" class="form-select mb-3">
                    <t t-foreach="this.props.managers" t-as="manager" t-key="manager.id">
                        <option t-att-value="manager.id" t-esc="manager.name"/>
                    </t>
                </select>
                <input type="password" t-model.proxy="this.state.pin" class="form-control mb-3" placeholder="Enter PIN" t-on-keyup="this._onPinKeyup"/>
            </div>
            <div class="footer">
                <button t-on-click="this.confirm" class="btn btn-primary">Confirm</button>
                <button t-on-click="this.cancel" class="btn btn-secondary">Cancel</button>
            </div>
        </div>`;

    props = useProps({
        title: t.string().optional(""),
        managers: t.array(),
        onConfirm: t.function(),
    });

    setup() {
        console.log("[ManagerSelectPopup] Setup iniciado");
        this.state = proxy({
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
        if (selectedManager._pin && selectedManager._pin === Sha1.hash(this.state.pin)) {
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
        <Dialog title="this.props.title" size="'md'">
            <ManagerSelectPopup
                title="this.props.title"
                managers="this.props.managers"
                onConfirm="this.props.onClose" 
            />
        </Dialog>`;
    
    static components = { Dialog, ManagerSelectPopup };
    props = useProps({
        title: t.string(),
        managers: t.array(),
        onClose: t.function(),
        close: t.function().optional(),
    });
}

// Template genérico que aparece después de hacer clic en "Close Register"
export class SessionCloseTemplatePopup extends Component {
    static template = xml`
        <div class="popup close-session-template">
            <div class="header">
                <h4><t t-esc="this.props.title"/></h4>
            </div>
            <div class="body">
                <div class="alert alert-info mb-3">
                    <div class="row">
                        <div class="col-md-6">
                            <h6><i class="fa fa-user"></i> Session Information</h6>
                            <p><strong>Manager:</strong> <t t-esc="this.props.managerName"/></p>
                            <p><strong>Sesión ID:</strong> <t t-esc="this.props.sessionId"/></p>
                            <p><strong>Cajero:</strong> <t t-esc="this.props.cashierName"/></p>
                        </div>
                        <div class="col-md-6">
                            <h6><i class="fa fa-clock-o"></i> Timing</h6>
                            <p><strong>Inicio de sesión:</strong> <t t-esc="this.props.sessionStart"/></p>
                            <p><strong>Hora de cierre:</strong> <t t-esc="this.props.currentDate"/></p>
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
                                            <t t-esc="this.env.utils.formatCurrency(this.props.cashData.expected || 0)"/>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <label class="text-muted">Contado:</label>
                                        <div class="h5" t-att-class="this.props.cashData.difference !== 0 ? 'text-warning' : 'text-success'">
                                            <t t-esc="this.env.utils.formatCurrency(this.props.cashData.counted || 0)"/>
                                        </div>
                                    </div>
                                </div>
                                <hr class="my-2"/>
                                <div class="row">
                                    <div class="col-12">
                                        <label class="text-muted">Diferencia:</label>
                                        <div class="h5" t-att-class="this.props.cashData.difference !== 0 ? 'text-danger' : 'text-success'">
                                            <t t-esc="this.env.utils.formatCurrency(this.props.cashData.difference || 0)"/>
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
                                            <t t-esc="this.props.salesData.totalOrders || 0"/>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <label class="text-muted">Cantidad Ttotal:</label>
                                        <div class="h5 text-primary">
                                            <t t-esc="this.env.utils.formatCurrency(this.props.salesData.totalAmount || 0)"/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Notas de cierre si existen -->
                <div t-if="this.props.closingNotes" class="card mb-3">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="fa fa-comment"></i> Closing Notes</h6>
                    </div>
                    <div class="card-body">
                        <p class="mb-0" t-esc="this.props.closingNotes"/>
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
                        <button t-on-click="this.proceedWithClose" class="btn btn-success">
                            <i class="fa fa-check"></i> Confirmar Cierre de sesión
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

    props = useProps({
        title: t.string().optional(""),
        managerName: t.string(),
        cashierName: t.string(),
        sessionId: t.or([t.string(), t.number()]),
        sessionStart: t.string(),
        currentDate: t.string(),
        cashData: t.object(),
        salesData: t.object(),
        closingNotes: t.string().optional(""),
        onConfirm: t.function(),
    });

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

// MODIFICACIÓN PRINCIPAL: Dialog personalizado sin botón OK automático
export class SessionCloseTemplateDialog extends Component {
    static template = xml`
        <div class="modal fade show d-block" tabindex="-1" role="dialog" style="background-color: rgba(0,0,0,0.5);">
            <div class="modal-dialog modal-xl" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h4 class="modal-title" t-esc="this.props.title"/>
                    </div>
                    <div class="modal-body p-0">
                        <SessionCloseTemplatePopup
                            title="this.props.title"
                            managerName="this.props.managerName"
                            cashierName="this.props.cashierName"
                            sessionId="this.props.sessionId"
                            sessionStart="this.props.sessionStart"
                            currentDate="this.props.currentDate"
                            cashData="this.props.cashData"
                            salesData="this.props.salesData"
                            closingNotes="this.props.closingNotes"
                            onConfirm="this.handleConfirm.bind(this)" 
                        />
                    </div>
                </div>
            </div>
        </div>`;
    
    static components = { SessionCloseTemplatePopup };
    props = useProps({
        title: t.string(),
        managerName: t.string(),
        cashierName: t.string(),
        sessionId: t.or([t.string(), t.number()]),
        sessionStart: t.string(),
        currentDate: t.string(),
        cashData: t.object(),
        salesData: t.object(),
        closingNotes: t.string().optional(""),
        onClose: t.function(),
        close: t.function().optional(),
    });

    handleConfirm(result) {
        console.log("[SessionCloseTemplateDialog] handleConfirm llamado con:", result);
        if (this.props.close) {
            this.props.close();
        }
        this.props.onClose(result);
    }
}

// Patch del ClosePosPopup para interceptar el clic en "Close Register"
// Patch del ClosePosPopup para interceptar el clic en "Close Register"
patch(ClosePosPopup.prototype, {
    async confirm() {
        console.log("[ClosePosPopup] Interceptando confirm() - botón Close Register presionado");
        
        // Obtener datos de la sesión actual antes de continuar
        const sessionData = this.getSessionDataForTemplate();
        
        // Mostrar el diálogo de validación de manager PRIMERO
        const managerValidationResult = await this.showManagerValidation();

        if (managerValidationResult?.confirmed) {
            console.log("[ClosePosPopup] Manager validado, saltando template y procediendo directo al cierre");

            // Registrar la aprobación del manager en el backend
            await this.registerManagerApproval(managerValidationResult);

            // Ejecutar cierre directamente
            return this.closeSession();

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
        const managerIds = this.pos.config.manager_employee_ids || [];
        const managers = this.pos.models["hr.employee"].getAll().filter(
            (employee) => managerIds.includes(employee.id) && employee._role === "manager"
        );
        
        console.log("[ClosePosPopup] Managers disponibles:", managers);

        if (!managers.length) {
            console.log("[ClosePosPopup] No hay managers configurados, saltando validación");
            return { confirmed: false };
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
