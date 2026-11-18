{
    'name': 'Desactivar QR en PDV',
    'version': '20.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'ERIK DMR',
    'website': 'https://sayrax.com',
    'summary': 'Check para desactivar impresion de QR en PDV individualmente',
    "depends": ["point_of_sale"],
    'assets': {
        'point_of_sale._assets_pos': [
        ],
    },
    'data': [
        'views/pos_config_views.xml',
        'views/pos_receipt_templates.xml',
    ],
    'installable': True,
}
