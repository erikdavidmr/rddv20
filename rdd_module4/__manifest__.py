{
    "name": "POS Validate Payment Zero Quantity",
    'version': '20.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Erik Miranda',
    "summary": "Previene pagos con líneas en cantidad cero en POS",
    "depends": ["point_of_sale"],
    "assets": {
        "point_of_sale._assets_pos": [
            "rdd_module4/static/src/js/pos_payment_validation.js",
        ],
    },
        "installable": True,
        "application": False,
}