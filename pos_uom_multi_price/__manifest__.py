# -*- coding: utf-8 -*-
{
    'name': "Multi-unit Price Management for POS Products",
    'version': '20.0.1.0.0',
    'summary': 'Point of Sale (POS) unit price by measure',
    'category': 'Point of Sale',
    'license': "AGPL-3",
    'description': """
        This module enables the sale of products in various units of measure within the POS system
    """,

    'author': 'BuildFish',
    'website': 'http://www.build-fish.com/',
    'sequence': 101,
    'depends': ['product', 'point_of_sale', 'account'],
    'data': [
        'security/ir.access.csv',
        'views/product_views.xml',
        'views/res_config_settings_view.xml',
        'views/pos_order_views.xml',
    ],
    'images': [
        'static/description/main_screenshot.png',
    ],
    'live_test_url': 'https://youtu.be/yi2MHUtOhm0',
    'price': 30.00,
    'currency': 'USD',
    'installable': True,
    'auto_install': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_uom_multi_price/static/src/**/*',
            #'pos_uom_multi_price/static/src/js/*',
        ],
    },
}
