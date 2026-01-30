# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = "res.users"

    def _meera_validate_driver_is_portal_only(self):
        """
        Driver / Rider login policy
        ---------------------------
        If the linked contact is marked as a Driver (res.partner.meera_is_driver),
        this user must NEVER be an Internal User (base.group_user).

        Reason: Internal users consume paid Odoo licenses. Drivers should be portal-only.
        Enforcement is done at ORM level to block UI/API/XMLRPC/CSV mistakes.
        """
        group_internal = self.env.ref("base.group_user", raise_if_not_found=False)
        if not group_internal:
            return

        for user in self:
            if user.partner_id and user.partner_id.meera_is_driver and group_internal in user.groups_id:
                raise ValidationError(_(
                    "This user is linked to a Driver contact. "
                    "Drivers must remain Portal-only and cannot be Internal Users."
                ))

    @api.constrains("groups_id", "partner_id")
    def _constrains_meera_driver_groups(self):
        self._meera_validate_driver_is_portal_only()

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._meera_validate_driver_is_portal_only()
        return users

    def write(self, vals):
        res = super().write(vals)
        self._meera_validate_driver_is_portal_only()
        return res
