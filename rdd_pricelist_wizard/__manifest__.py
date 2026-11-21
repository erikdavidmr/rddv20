# -*- coding: utf-8 -*-
{
    'name': 'RDD - Asistente de Asignación de Precios',
    'version': '20.0.1.0.0',
    'summary': 'Asistente rápido para asignar precios regulares, mayoreo y promociones a listas base y derivadas.',
    'category': 'Sales/Point of Sale',
    'author': 'Sayrax / RDD',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'point_of_sale',
        'rdd_module',
    ],
    'data': [
        'security/ir.access.csv',
        'wizard/pricelist_assign_wizard_views.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
