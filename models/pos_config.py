# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    allowed_order_type_ids = fields.Many2many(
        comodel_name="pos.order.type",
        relation="pos_config_pos_order_type_rel",
        column1="config_id",
        column2="order_type_id",
        string="Allowed Order Types",
        help="Restrict which order types can be used in this POS configuration.",
    )
