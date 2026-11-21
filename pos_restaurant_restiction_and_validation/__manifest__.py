# -*- coding: utf-8 -*-
#################################################################################
#
#  Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#  See LICENSE file for full copyright and licensing details.
#  License URL : <https://store.webkul.com/license.html/>
#
#################################################################################
{
  'name': 'Pos Restaurant Restrictions and Validations (with Remote OTP)',
  'version': '20.0.1.2.0',
  'author': 'Webkul Software Pvt. Ltd., gerardosarracino, Antigravity',
  'category': 'Point of Sale',
  'sequence': 1,
  'summary': '''The Odoo POS Restaurant Restrictions and Validations Module enhances POS security by restricting employees from deleting order lines, orders or closing sessions without manager PIN or single-use Remote OTP via Email/WhatsApp.''',
  'description': """Enhances POS security with line deletion, order cancellation, and session close restrictions. Supports direct manager PIN entry (without manager dropdowns) and single-use dynamic OTP delivered by email with cash audit details for multi-branch remote approvals.""",
  'depends': ['point_of_sale', 'pos_restaurant', 'hr', 'pos_hr', 'mail'],
  'data': [
    'security/ir.access.csv',
    'data/mail_template_data.xml',
    'views/pos_config_view.xml',
    'views/pos_manager_approval_view.xml',
  ],
  'installable': True,
  'application': True,
  'assets': {
    'point_of_sale._assets_pos': [
      'pos_restaurant_restiction_and_validation/static/src/screens/popUps/deny_popUp.js',
      'pos_restaurant_restiction_and_validation/static/src/app/decrease_quantity_by_manager.js',
      'pos_restaurant_restiction_and_validation/static/src/app/session_close_by_manager.js',
      'pos_restaurant_restiction_and_validation/static/src/app/delete_by_manager.js',
      'pos_restaurant_restiction_and_validation/static/src/screens/popUps/deny_popUp.xml',
    ],
    'point_of_sale._assets': [
      'pos_restaurant_restiction_and_validation/static/src/app/session_close_by_manager.js',
    ],
  },
  'images': ['static/description/Banner.png'],
  'license': 'Other proprietary',
}
