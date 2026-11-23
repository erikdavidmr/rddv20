# -*- coding: utf-8 -*-
{
    'name': "RDD Custom Module",

    'summary': """
        Modulo para el RDD donde se incluyen customizaciones en los modulos de point of sale, inventory y Listprice""",

    'description': """

    """,

    'author': "gerardosarracino,erikdmr",
    'license': 'OPL-1',
    'category': 'Project',
    'version': '20.0.2.0.0',
    'depends': ['base', 'mail', 'point_of_sale', 'product', 'sale', 'stock','stock_delivery', 'l10n_mx_edi', 'purchase', 'hr'],

    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'security/ir_rules.xml',
        'data/cron.xml',
        'views/res_users.xml',
        'views/pricelist.xml',
        'views/pos_config.xml',
        'views/product.xml',
        'views/pricelist_issue_views.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            'rdd_module/static/src/scss/studio_icon.scss',
        ],
        'point_of_sale.assets': [
            "rdd_module/static/src/app/models/*",
            "rdd_module/static/src/app/navbar/closing_popup/closing_popup.xml",
        ],
        'point_of_sale._assets_pos': [
            "rdd_module/static/src/app/models/*",
            "rdd_module/static/src/app/navbar/closing_popup/closing_popup.xml",
        ],
        'point_of_sale.customer_display_assets': [
            ('include', 'point_of_sale.base_app'),
        ],
    },

    
    'images': [],
    'demo': [
    ],
}
