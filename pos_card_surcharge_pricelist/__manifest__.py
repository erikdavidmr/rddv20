# -*- coding: utf-8 -*-
{
    'name': 'POS Card Surcharge Pricelist (+2%)',
    'version': '20.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Conmutación automática de tarifa con tarjeta (+2%) en Punto de Venta Odoo 20',
    'description': """
        Módulo para Punto de Venta Odoo 20:
        - Conmutación automática a tarifa con tarjeta (+2%) al seleccionar método de pago tarjeta o terminal.
        - Reversión automática a tarifa en efectivo al cancelar el pago con tarjeta.
        - Botón conmutador en la barra de navegación [ 💵 Efectivo ] / [ 💳 Tarjeta (+2%) ].
        - Mapeo inteligente con tarifas 2.0 existentes en el catálogo.
        - Cálculo de impuestos exactos (IVA e IEPS) por producto para ticket y Factura Global.
    """,
    'author': 'Antigravity, erikdmr',
    'license': 'OPL-1',
    'depends': ['point_of_sale', 'product'],
    'data': [
        'views/pos_payment_method_views.xml',
        'views/pos_config_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_card_surcharge_pricelist/static/src/app/card_surcharge.scss',
            'pos_card_surcharge_pricelist/static/src/app/utils/card_pricelist_utils.js',
            'pos_card_surcharge_pricelist/static/src/app/overrides/payment_screen.js',
            'pos_card_surcharge_pricelist/static/src/app/card_surcharge_toggle/card_surcharge_toggle.js',
            'pos_card_surcharge_pricelist/static/src/app/card_surcharge_toggle/card_surcharge_toggle.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
