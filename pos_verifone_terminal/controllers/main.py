from odoo import http
from odoo.http import request
import logging
import json
import re
import traceback
import requests


_logger = logging.getLogger(__name__)


class VerifoneWebhook(http.Controller):

    @http.route('/verifone/webhook_pago', type='jsonrpc', auth='none', csrf=False)
    def webhook_pago(self):
        try:
            # 🔒 Validar token de cabecera
            token = request.httprequest.headers.get("X-Verifone-Token")
            expected_token = request.env["ir.config_parameter"].sudo().get_str("verifone.webhook.token")

            _logger.info(f"[Verifone] Token recibido: {token}")
            _logger.info(f"[Verifone] Token esperado: {expected_token}")

            if not expected_token or token != expected_token:
                _logger.warning("[Verifone] Token inválido o ausente")
                return {"error": "Unauthorized"}, 401

            # 📦 Obtener payload JSON
            payload = request.httprequest.get_json(silent=True)
            if not payload:
                _logger.warning("[Verifone] Payload vacío o malformado")
                return {"status": "empty_payload"}, 200

            _logger.info("[Verifone] Payload recibido: %s", payload)

            # 🎯 Validar external_reference
            external_reference = payload.get("external_reference")
            pattern = r"(\d+)_(\d+)_([0-9a-f\-]+)"
            match = re.fullmatch(pattern, external_reference or "")
            if not match:
                _logger.warning("[Verifone] external_reference mal formado o ausente: %s", external_reference)
                return {"status": "bad_reference"}, 200

            session_id, method_id, uuid = match.groups()
            session = request.env["pos.session"].sudo().browse(int(session_id))

            if not session or session.state != "opened":
                _logger.warning("[Verifone] Sesión POS inválida o cerrada: %s", session_id)
                return {"status": "invalid_session"}, 200

            # 🔁 Notificar al POS
            payload["type"] = "VERIFONE_LATEST_RESPONSE"
            _logger.info("[Verifone] Enviando a POS '%s'", session.config_id.name)
            _logger.info("[Verifone] Payload a enviar: %s", json.dumps(payload))

            try:
                session.config_id._notify("VERIFONE_LATEST_RESPONSE", payload)
                _logger.info(f"[Verifone] Notificación enviada correctamente al POS '{session.config_id.name}'")
            except Exception as e:
                _logger.error("[Verifone] Error enviando notificación al POS: %s", str(e))
                _logger.debug(traceback.format_exc())

            return {"status": "ok"}

        except Exception:
            _logger.error("[Verifone] Excepción procesando webhook:\n%s", traceback.format_exc())
            return {"error": "internal_error"}, 500

    @http.route('/verifone/proxy', type='http', auth='user', csrf=False)
    def proxy_to_middleware(self, **payload):
        try:
            payload = json.loads(request.httprequest.data)
            external_reference = payload.get("external_reference", "")
            if not external_reference:
                return request.make_response(
                    json.dumps({"status": "error", "message": "Missing external_reference"}),
                    headers=[("Content-Type", "application/json")],
                    status=400
                )

            session_id, method_id, _ = external_reference.split("_")
            payment_method = request.env["pos.payment.method"].sudo().browse(int(method_id))

            # url = f"http://{ip}:{port}/pay"

            # Adecuacion por dominio

            ip = payment_method.verifone_middleware_ip
            port = payment_method.verifone_middleware_port

            # ✅ Validar primero
            if not ip:
                return request.make_response(
                    json.dumps({"status": "error", "message": "IP o dominio no configurado"}),
                    headers=[("Content-Type", "application/json")],
                    status=400
                )

            if not port or not (1 <= int(port) <= 65535):
                return request.make_response(
                    json.dumps({"status": "error", "message": "Puerto inválido"}),
                    headers=[("Content-Type", "application/json")],
                    status=400
                )

            # ✅ Construcción de URL segura
            if (".com" in ip or ".net" in ip or "." in ip) and int(port) in (443, 8443):
                url = f"https://{ip}/pay"
            else:
                url = f"http://{ip}:{port}/pay"

            _logger.info("[Verifone Proxy] Enviando a middleware: %s", url)
            _logger.debug("[Verifone Proxy] Payload: %s", payload)

            response = requests.post(url, json=payload, timeout=10)

            # Formato seguro para retornar al frontend
            return request.make_response(
                json.dumps(response.json()),
                headers=[("Content-Type", "application/json")],
                status=response.status_code
            )

        except Exception as e:
            _logger.exception("[Verifone Proxy] Error:")
            return request.make_response(
                json.dumps({"status": "error", "message": str(e)}),
                headers=[("Content-Type", "application/json")],
                status=500
            )


