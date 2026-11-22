# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)


class RddPricelistIssue(models.Model):
    _name = 'rdd.pricelist.issue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Incidencias en Cambio de Tarifas TPV'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Título',
        required=True,
        tracking=True,
        default=lambda self: _('Incidencia de Tarifa TPV')
    )
    date = fields.Datetime(
        string='Fecha y Hora',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )
    pos_config_id = fields.Many2one(
        'pos.config',
        string='Caja / TPV',
        required=True,
        tracking=True,
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Sucursal',
        related='pos_config_id.company_id',
        store=True,
        readonly=True
    )
    current_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Tarifa Mantenida en Caja',
        tracking=True,
        help='Tarifa con la que se quedó cobrando la caja al no poder aplicar cambio'
    )
    issue_type = fields.Selection([
        ('no_candidate', 'Sin tarifa programada para hoy/horario'),
        ('exception', 'Error técnico de ejecución'),
    ], string='Tipo de Incidencia', default='no_candidate', required=True, tracking=True)

    details = fields.Text(
        string='Detalles Técnicos',
        help='Explicación de las condiciones evaluadas y motivo del fallo'
    )
    state = fields.Selection([
        ('pending', 'Pendiente de Atención'),
        ('resolved', 'Resuelto'),
    ], string='Estado', default='pending', required=True, index=True, tracking=True)

    resolved_by = fields.Many2one(
        'res.users',
        string='Resuelto por',
        readonly=True,
        tracking=True
    )
    resolved_date = fields.Datetime(
        string='Fecha de Resolución',
        readonly=True,
        tracking=True
    )
    resolution_notes = fields.Text(
        string='Notas de Solución',
        tracking=True,
        help='Explicación de la acción tomada para corregir la incidencia (ej: se configuró horario para jueves)'
    )

    def action_mark_resolved(self):
        for rec in self:
            rec.write({
                'state': 'resolved',
                'resolved_by': self.env.user.id,
                'resolved_date': fields.Datetime.now(),
            })
            notes = f" Notas: {rec.resolution_notes}" if rec.resolution_notes else ""
            rec.message_post(body=f"✅ Incidencia marcada como <b>Resuelta</b> por {self.env.user.name}.{notes}")

    def action_reopen(self):
        for rec in self:
            rec.write({
                'state': 'pending',
                'resolved_by': False,
                'resolved_date': False,
            })
            rec.message_post(body=f"⚠️ Incidencia <b>Reabierta</b> por {self.env.user.name}.")

