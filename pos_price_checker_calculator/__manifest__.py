# -*- coding: utf-8 -*-
{
    'name': 'POS Price Checker & Bulk Calculator',
    'version': '20.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Buscador y Calculadora de Precios y Granel para Punto de Venta',
    'description': """
        Módulo para Punto de Venta Odoo 20:
        - Buscador ágil de precios sin agregar líneas al ticket (evita autorizaciones de gerente).
        - Calculadora bidireccional Dinero ($) <---> Gramos / Kilos para venta a granel.
        - Detección automática y conmutación entre presentaciones (A Granel, Paquetes, Cajas).
        - Botón de acción rápida en Navbar y atajo de teclado F4.
        - Botón para agregar al ticket con la cantidad exacta calculada.
    """,
    'author': 'Antigravity, erikdmr',
    'license': 'OPL-1',
    'depends': ['point_of_sale', 'product'],
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_price_checker_calculator/static/src/app/price_calculator.scss',
            'pos_price_checker_calculator/static/src/app/price_calculator_popup/price_calculator_popup.js',
            'pos_price_checker_calculator/static/src/app/price_calculator_popup/price_calculator_popup.xml',
            'pos_price_checker_calculator/static/src/app/price_calculator_button/price_calculator_button.js',
            'pos_price_checker_calculator/static/src/app/price_calculator_button/price_calculator_button.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
