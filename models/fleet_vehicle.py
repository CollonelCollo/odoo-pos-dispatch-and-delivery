# -*- coding: utf-8 -*-
import secrets

from odoo import api, fields, models


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    # -------------------------------------------------------------------------
    # Tracking (telemetry) - WRITABLE base fields
    # -------------------------------------------------------------------------
    last_lat = fields.Float("Last Latitude")
    last_lng = fields.Float("Last Longitude")
    last_loc_time = fields.Datetime("Last Location Time")

    # -------------------------------------------------------------------------
    # Compatibility aliases (READONLY related) - DO NOT WRITE TO THESE
    # -------------------------------------------------------------------------
    dispatch_last_latitude = fields.Float(
        string="Dispatch Last Latitude",
        related="last_lat",
        store=True,
        readonly=True,
    )
    dispatch_last_longitude = fields.Float(
        string="Dispatch Last Longitude",
        related="last_lng",
        store=True,
        readonly=True,
    )
    dispatch_last_update = fields.Datetime(
        string="Dispatch Last Update",
        related="last_loc_time",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Dispatch configuration
    # -------------------------------------------------------------------------
    is_dispatch_vehicle = fields.Boolean(
        string="Use for Dispatch",
        help="Enable if this vehicle can be assigned to dispatch delivery jobs.",
        default=False,
    )

    dispatch_driver_id = fields.Many2one(
        "res.partner",
        string="Default Driver",
        help="Driver assigned to this vehicle (used for dispatch and driver app token mapping).",
        ondelete="set null",
    )

    dispatch_capacity_kg = fields.Float(
        string="Capacity (KG)",
        help="Optional capacity reference for dispatch planning.",
    )

    dispatch_open_orders_count = fields.Integer(
        string="Open Dispatch Jobs",
        compute="_compute_dispatch_open_load",
        store=False,
    )
    dispatch_open_weight_kg = fields.Float(
        string="Open Weight (KG)",
        compute="_compute_dispatch_open_load",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Driver Token (single source of truth = res.partner.meera_driver_token)
    # -------------------------------------------------------------------------
    dispatch_driver_token = fields.Char(
        string="Driver Tracking Token",
        related="dispatch_driver_id.meera_driver_token",
        store=True,
        readonly=True,
        help="Mirrors the driver's token from res.partner.meera_driver_token. This is the only supported token source for the driver app.",
    )

    def action_generate_driver_tracking_token(self):
        """
        Rotate the driver's token.

        Important:
        - We do NOT store a separate token on the vehicle to avoid duplicates and mismatches.
        - The only supported token is res.partner.meera_driver_token.
        """
        for rec in self:
            if rec.dispatch_driver_id and "meera_driver_token" in rec.dispatch_driver_id._fields:
                # Use partner method if available, otherwise generate here (64-char hex like Contact button)
                if hasattr(rec.dispatch_driver_id, "action_generate_driver_token"):
                    rec.dispatch_driver_id.action_generate_driver_token()
                else:
                    token = secrets.token_hex(32)
                    rec.dispatch_driver_id.sudo().write({"meera_driver_token": token})
        return True

    # -------------------------------------------------------------------------
    # Compute dispatch load
    # -------------------------------------------------------------------------
    @api.depends("is_dispatch_vehicle")
    def _compute_dispatch_open_load(self):
        Dispatch = self.env["meera.dispatch.order"].sudo()
        open_states = ("waiting", "assigned", "enroute", "pending", "draft")

        for vehicle in self:
            if not vehicle.is_dispatch_vehicle:
                vehicle.dispatch_open_orders_count = 0
                vehicle.dispatch_open_weight_kg = 0.0
                continue

            vehicle.dispatch_open_orders_count = Dispatch.search_count(
                [("vehicle_id", "=", vehicle.id), ("state", "in", open_states)]
            )

            vehicle.dispatch_open_weight_kg = 0.0
