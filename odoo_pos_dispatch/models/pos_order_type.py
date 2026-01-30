# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrderType(models.Model):
    """Master data for POS Order Types, e.g. Dine-in, Takeaway, Delivery."""
    _name = "pos.order.type"
    _description = "POS Order Type"
    _order = "sequence, id"

    name = fields.Char(required=True, index=True)
    code = fields.Char(string="Code", index=True)
    sequence = fields.Integer(default=10)

    # Allow global (company_id False) or company-specific types
    company_id = fields.Many2one("res.company", string="Company", index=True)

    # Flags used by UI + logic
    is_delivery = fields.Boolean(
        string="Delivery",
        help="If checked, selecting this order type will ask for a delivery address.",
        index=True,
    )
    is_dine_in = fields.Boolean(string="Dine-In", index=True)
    is_takeaway = fields.Boolean(string="Takeaway", index=True)

    active = fields.Boolean(default=True)

    # Reverse link to POS configs (MUST match pos.config.allowed_order_type_ids)
    config_ids = fields.Many2many(
        comodel_name="pos.config",
        relation="pos_config_pos_order_type_rel",
        column1="order_type_id",
        column2="config_id",
        string="POS Configs",
    )

    @api.constrains("company_id", "config_ids")
    def _check_company_consistency(self):
        for rec in self:
            # If order type is company-specific, its configs must match that company
            if rec.company_id and rec.config_ids and any(
                c.company_id and c.company_id != rec.company_id for c in rec.config_ids
            ):
                raise ValueError("POS Configs must belong to the same company as the POS Order Type.")
