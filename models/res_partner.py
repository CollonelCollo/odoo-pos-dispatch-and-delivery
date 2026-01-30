# -*- coding: utf-8 -*-
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    meera_driver_token = fields.Char(
        string="Driver Tracking Token",
        help="Token used by the Driver Mobile App for authentication.",
        copy=False,
        readonly=True,
    )

    meera_is_driver = fields.Boolean(
        string="Is Driver",
        help="Tick if this contact is used as a delivery driver. Drivers are enforced as Portal-only users.",
        default=False,
        index=True,
    )

    # Read-only mirror for non-managers to view status without edit rights
    meera_is_driver_ro = fields.Boolean(
        string="Is Driver?",
        compute="_compute_meera_is_driver_ro",
        store=False,
        readonly=True,
        help="Read-only mirror of 'Is Driver' for non-managers.",
    )

    def _compute_meera_is_driver_ro(self):
        for partner in self:
            partner.meera_is_driver_ro = bool(partner.meera_is_driver)

    meera_driver_user_id = fields.Many2one(
        "res.users",
        string="Driver User",
        compute="_compute_meera_driver_user_id",
        store=False,
        help="The user account linked to this driver contact (if any).",
    )

    def _compute_meera_driver_user_id(self):
        Users = self.env["res.users"].sudo()
        for partner in self:
            partner.meera_driver_user_id = Users.search([("partner_id", "=", partner.id)], limit=1)

    # -------------------------------------------------------------------------
    # Security: restrict editing of meera_is_driver
    # -------------------------------------------------------------------------
    def _meera_can_edit_driver_flag(self):
        """Only Dispatch Managers (and Settings/Admin) may toggle driver flag."""
        user = self.env.user
        if self.env.is_superuser():
            return True
        if user.has_group("base.group_system"):
            return True
        if user.has_group("odoo_pos_dispatch.group_meera_dispatch_manager"):
            return True
        return False

    def write(self, vals):
        if "meera_is_driver" in vals and not self._meera_can_edit_driver_flag():
            raise UserError(_("You are not allowed to change 'Is Driver'. Please contact a Dispatch Manager."))
        return super().write(vals)

    # -------------------------------------------------------------------------
    # Token & portal user flows
    # -------------------------------------------------------------------------
    def action_generate_driver_token(self):
        """Generate a new random token for the driver."""
        for partner in self:
            token = secrets.token_hex(32)  # 64-char hex token
            partner.write({"meera_driver_token": token})
        return True

    def action_create_meera_driver_portal_user(self):
        """
        Create a Portal-only user for this partner (driver/rider).
        """
        self.ensure_one()

        if not self.meera_is_driver:
            self.meera_is_driver = True

        if not self.email:
            raise UserError(_("Please set an Email on the Driver contact before creating a login."))

        existing_user = self.env["res.users"].sudo().search([("partner_id", "=", self.id)], limit=1)
        if existing_user:
            raise UserError(_("A user already exists for this Driver contact."))

        if not self.meera_driver_token:
            self.action_generate_driver_token()

        group_driver_portal = self.env.ref("odoo_pos_dispatch.group_meera_driver_portal", raise_if_not_found=False)
        if not group_driver_portal:
            raise UserError(_("Driver Portal security group is missing. Please update the module."))

        user = (
            self.env["res.users"]
            .sudo()
            .with_context(no_reset_password=True)
            .create({
                "name": self.name or self.email,
                "login": self.email,
                "partner_id": self.id,
                "groups_id": [(6, 0, [group_driver_portal.id])],
                "active": True,
            })
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Driver User"),
            "res_model": "res.users",
            "view_mode": "form",
            "res_id": user.id,
            "target": "current",
        }
