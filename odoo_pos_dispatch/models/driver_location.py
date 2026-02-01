# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MeeraDriverLocation(models.Model):
    _name = "meera.driver.location"
    _description = "Real-time Driver Location"
    _order = "timestamp desc, id desc"

    # ------------------------------------------------------------
    # CORE
    # ------------------------------------------------------------
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicle",
        required=True,
        index=True,
        ondelete="cascade",
    )

    driver_id = fields.Many2one(
        "res.partner",
        string="Driver",
        required=False,
        help="Driver partner resolved from the vehicle configuration.",
        index=True,
        ondelete="set null",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        default=lambda self: self.env.company,
        help="Derived from the vehicle company where possible.",
    )

    lat = fields.Float(string="Latitude", digits=(16, 8), required=True)
    lng = fields.Float(string="Longitude", digits=(16, 8), required=True)
    accuracy = fields.Float(string="Accuracy (m)")

    timestamp = fields.Datetime(
        string="Timestamp",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )

    maps_url = fields.Char(
        string="Google Maps Link",
        compute="_compute_maps_url",
        store=False,
    )

    # ------------------------------------------------------------
    # COMPUTES
    # ------------------------------------------------------------
    @api.depends("lat", "lng")
    def _compute_maps_url(self):
        for rec in self:
            if rec.lat and rec.lng:
                rec.maps_url = "https://maps.google.com/?q=%s,%s" % (rec.lat, rec.lng)
            else:
                rec.maps_url = False

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------
    def _driver_from_vehicle(self, vehicle):
        if not vehicle:
            return False
        if "dispatch_driver_id" in vehicle._fields and vehicle.dispatch_driver_id:
            return vehicle.dispatch_driver_id
        if "driver_id" in vehicle._fields and vehicle.driver_id:
            return vehicle.driver_id
        return False

    def _normalize_vals_from_vehicle(self, vals):
        if not vals.get("vehicle_id"):
            return vals

        vehicle = self.env["fleet.vehicle"].browse(vals["vehicle_id"]).exists()
        if not vehicle:
            return vals

        if "company_id" not in vals:
            v_company = getattr(vehicle, "company_id", False)
            vals["company_id"] = v_company.id if v_company else False

        if "driver_id" not in vals:
            driver = self._driver_from_vehicle(vehicle)
            vals["driver_id"] = driver.id if driver else False

        return vals

    # ------------------------------------------------------------
    # ORM OVERRIDES
    # ------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        fixed = []
        for vals in vals_list:
            vals = dict(vals or {})
            vals = self._normalize_vals_from_vehicle(vals)
            fixed.append(vals)
        return super().create(fixed)

    def write(self, vals):
        vals = dict(vals or {})
        vals = self._normalize_vals_from_vehicle(vals)
        return super().write(vals)

    # ------------------------------------------------------------
    # RETENTION CRON
    # ------------------------------------------------------------
    @api.model
    def cron_prune_locations(self, days=30, limit=50000):
        """
        Deletes driver location rows older than N days.
        - days: retention window (default 30)
        - limit: safety batch size per cron run
        """
        try:
            days = int(days)
        except Exception:
            days = 30

        if days <= 0:
            days = 7

        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)

        domain = [("timestamp", "<", cutoff)]
        old_ids = self.sudo().search(domain, order="timestamp asc, id asc", limit=int(limit)).ids
        if old_ids:
            self.sudo().browse(old_ids).unlink()

        return True
