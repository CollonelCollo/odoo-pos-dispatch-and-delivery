# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MeeraDispatchOrder(models.Model):
    _name = "meera.dispatch.order"
    _description = "Meera Dispatch Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, id desc"

    _sql_constraints = [
        ("uniq_pos_order", "unique(pos_order_id)", "Only one dispatch job is allowed per POS order."),
    ]

    # -------------------------------------------------------------------------
    # BASIC FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Dispatch Reference",
        required=True,
        default="New",
        copy=False,
        tracking=True,
        index=True,
    )

    pos_order_id = fields.Many2one(
        "pos.order",
        string="POS Order",
        tracking=True,
        ondelete="set null",
        index=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        tracking=True,
        ondelete="set null",
        index=True,
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Customer (Alias)",
        related="partner_id",
        store=True,
        readonly=False,
    )

    customer_phone = fields.Char(string="Customer Phone", tracking=True)
    note = fields.Text(string="Notes", tracking=True)

    # -------------------------------------------------------------------------
    # ORDER TYPE (MIRROR POS ORDER TYPE MODULE)
    # -------------------------------------------------------------------------
    order_type = fields.Selection(
        [
            ("delivery", "Delivery"),
            ("takeaway", "Takeaway"),
            ("dine_in", "Dine In"),
        ],
        string="Order Type",
        required=True,
        index=True,
        tracking=True,
        default="delivery",
        help="Mirrors the POS Order Type logic (Delivery / Takeaway / Dine In).",
    )

    pos_order_type_id = fields.Many2one(
        "pos.order.type",
        string="POS Order Type",
        related="pos_order_id.order_type_id",
        store=True,
        readonly=True,
        help="Mirror of pos.order.order_type_id computed by the POS Order Type module.",
    )

    pos_is_delivery = fields.Boolean(related="pos_order_id.is_delivery", store=True, readonly=True)
    pos_is_dine_in = fields.Boolean(related="pos_order_id.is_dine_in", store=True, readonly=True)
    pos_is_takeaway = fields.Boolean(related="pos_order_id.is_takeaway", store=True, readonly=True)

    # -------------------------------------------------------------------------
    # ADDRESSES & GEO
    # -------------------------------------------------------------------------
    pickup_address = fields.Text(string="Pickup Address", tracking=True)
    delivery_address = fields.Text(string="Delivery Address", tracking=True)

    delivery_latitude = fields.Float(string="Delivery Latitude", digits=(16, 7), tracking=True)
    delivery_longitude = fields.Float(string="Delivery Longitude", digits=(16, 7), tracking=True)

    delivery_note = fields.Text(string="Delivery Note", tracking=True)

    # -------------------------------------------------------------------------
    # DELIVERY MAP (CUSTOMER DESTINATION)
    # -------------------------------------------------------------------------
    delivery_map_url = fields.Char(
        string="Delivery Map Link",
        compute="_compute_delivery_map_url",
        store=False,
    )

    @api.depends("delivery_latitude", "delivery_longitude")
    def _compute_delivery_map_url(self):
        for rec in self:
            lat = rec.delivery_latitude
            lng = rec.delivery_longitude
            if lat and lng:
                rec.delivery_map_url = (
                    "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=18/%s/%s"
                    % (lat, lng, lat, lng)
                )
            else:
                rec.delivery_map_url = False

    def action_open_delivery_map(self):
        self.ensure_one()
        if not (self.delivery_latitude and self.delivery_longitude):
            raise UserError(_("No delivery coordinates set for this dispatch job."))
        return {"type": "ir.actions.act_url", "url": self.delivery_map_url, "target": "new"}

    # -------------------------------------------------------------------------
    # COMPANY
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    # -------------------------------------------------------------------------
    # AMOUNT & CURRENCY (SYNCED FROM POS)
    # -------------------------------------------------------------------------
    amount_total = fields.Monetary(
        string="Total Amount",
        currency_field="currency_id",
        tracking=True,
        compute="_compute_amount_and_currency",
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        compute="_compute_amount_and_currency",
        store=True,
        readonly=True,
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends(
        "pos_order_id",
        "pos_order_id.amount_total",
        "pos_order_id.currency_id",
        "pos_order_id.pricelist_id",
        "company_id",
    )
    def _compute_amount_and_currency(self):
        for rec in self:
            order = rec.pos_order_id
            if order:
                amount = order.amount_total or 0.0
                currency = order.currency_id or (
                    order.pricelist_id.currency_id if getattr(order, "pricelist_id", False) else None
                )
                currency = currency or rec.company_id.currency_id
            else:
                amount = 0.0
                currency = rec.company_id.currency_id

            rec.amount_total = amount
            rec.currency_id = currency

    # -------------------------------------------------------------------------
    # PRIORITY
    # -------------------------------------------------------------------------
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")],
        string="Priority",
        default="0",
        index=True,
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # VEHICLE & DRIVER
    # -------------------------------------------------------------------------
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicle",
        tracking=True,
        ondelete="set null",
        index=True,
    )

    driver_id = fields.Many2one(
        "res.partner",
        string="Driver",
        domain=[("is_company", "=", False)],
        tracking=True,
        ondelete="set null",
        index=True,
    )

    driver_phone = fields.Char(
        string="Driver Phone",
        compute="_compute_driver_phone",
        store=True,
        readonly=True,
    )

    can_call_driver = fields.Boolean(
        string="Can Call Driver",
        compute="_compute_can_call_driver",
        store=False,
    )

    # -------------------------------------------------------------------------
    # STAFF AUDIT
    # -------------------------------------------------------------------------
    assigned_by_uid = fields.Many2one(
        "res.users",
        string="Assigned By",
        required=False,
        ondelete="set null",
        index=True,
    )

    # -------------------------------------------------------------------------
    # ORDER TIME (RESTORED — FIXES YOUR VIEW)
    # -------------------------------------------------------------------------
    order_time = fields.Datetime(
        string="Order Time",
        default=fields.Datetime.now,
        tracking=True,
        index=True,
        help="Timestamp used for dispatch sorting/monitoring (shown in list/kanban).",
    )

    # -------------------------------------------------------------------------
    # DRIVER HELPERS
    # -------------------------------------------------------------------------
    def _get_driver_from_vehicle(self, vehicle):
        if not vehicle:
            return False
        if "dispatch_driver_id" in vehicle._fields and vehicle.dispatch_driver_id:
            return vehicle.dispatch_driver_id
        if "driver_id" in vehicle._fields and vehicle.driver_id:
            return vehicle.driver_id
        return False

    def _get_effective_driver_partner(self):
        self.ensure_one()
        if self.driver_id:
            return self.driver_id
        return self._get_driver_from_vehicle(self.vehicle_id)

    @api.onchange("vehicle_id")
    def _onchange_vehicle_id_set_driver(self):
        for rec in self:
            if not rec.vehicle_id:
                rec.driver_id = False
                return
            if not rec.driver_id:
                driver = rec._get_driver_from_vehicle(rec.vehicle_id)
                rec.driver_id = driver

    def _ensure_driver_from_vehicle_vals(self, vals):
        if not vals.get("vehicle_id"):
            return vals
        if "driver_id" in vals:
            return vals

        vehicle = self.env["fleet.vehicle"].browse(vals["vehicle_id"]).exists()
        if not vehicle:
            return vals

        driver = self._get_driver_from_vehicle(vehicle)
        if driver:
            vals["driver_id"] = driver.id
        return vals

    @api.depends(
        "driver_id",
        "driver_id.phone",
        "driver_id.mobile",
        "vehicle_id",
        "vehicle_id.dispatch_driver_id",
        "vehicle_id.dispatch_driver_id.phone",
        "vehicle_id.dispatch_driver_id.mobile",
        "vehicle_id.driver_id",
        "vehicle_id.driver_id.phone",
        "vehicle_id.driver_id.mobile",
    )
    def _compute_driver_phone(self):
        for rec in self:
            p = rec._get_effective_driver_partner()
            rec.driver_phone = ((p.phone or "").strip() or (p.mobile or "").strip()) if p else ""

    @api.depends("driver_phone", "state")
    def _compute_can_call_driver(self):
        for rec in self:
            rec.can_call_driver = bool((rec.driver_phone or "").strip()) and rec.state == "enroute"

    # -------------------------------------------------------------------------
    # LIVE VEHICLE LOCATION (RELATED)
    # -------------------------------------------------------------------------
    vehicle_last_latitude = fields.Float(related="vehicle_id.dispatch_last_latitude", readonly=True)
    vehicle_last_longitude = fields.Float(related="vehicle_id.dispatch_last_longitude", readonly=True)
    vehicle_last_location_time = fields.Datetime(related="vehicle_id.dispatch_last_update", readonly=True)

    def action_open_vehicle_map(self):
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError(_("No vehicle is linked to this dispatch job."))

        if hasattr(self.vehicle_id, "action_open_live_location"):
            return self.vehicle_id.action_open_live_location()

        lat = getattr(self.vehicle_id, "dispatch_last_latitude", 0.0) or getattr(self.vehicle_id, "last_lat", 0.0) or 0.0
        lng = getattr(self.vehicle_id, "dispatch_last_longitude", 0.0) or getattr(self.vehicle_id, "last_lng", 0.0) or 0.0
        if not lat or not lng:
            raise UserError(_("No live location has been received for this vehicle yet."))

        url = f"https://www.google.com/maps?q={lat},{lng}&z=18"
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    # -------------------------------------------------------------------------
    # STATE (CANONICAL) + ALIAS
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("waiting", "Waiting"),
            ("assigned", "Assigned"),
            ("enroute", "En Route"),
            ("delivered", "Delivered"),
            ("failed", "Failed"),
            ("cancel", "Cancelled"),
            ("draft", "Draft"),
            ("pending", "Pending Assignment"),
        ],
        string="Status",
        default="waiting",
        tracking=True,
        index=True,
        group_expand="_expand_state_groups",
    )

    dispatch_state = fields.Selection(
        related="state",
        string="Dispatch State",
        store=True,
        readonly=False,
    )

    @api.model
    def _expand_state_groups(self, states, domain, order=None):
        return ["waiting", "assigned", "enroute", "delivered", "failed", "cancel"]

    # -------------------------------------------------------------------------
    # HARDENING RULES
    # -------------------------------------------------------------------------
    _TERMINAL_STATES = {"delivered", "failed", "cancel"}

    _ALLOWED_TRANSITIONS = {
        "draft": {"waiting", "pending", "cancel"},
        "pending": {"waiting", "assigned", "cancel"},
        "waiting": {"assigned", "enroute", "cancel", "failed"},
        "assigned": {"enroute", "cancel", "failed"},
        "enroute": {"delivered", "failed", "cancel"},
        "delivered": set(),
        "failed": set(),
        "cancel": set(),
    }

    def _validate_state_transition(self, old_state, new_state):
        if old_state == new_state:
            return
        allowed = self._ALLOWED_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise UserError(_("Illegal dispatch state transition: %s → %s") % (old_state, new_state))

    # -------------------------------------------------------------------------
    # ALLOWED ACTIONS (for UI + Android app)
    # -------------------------------------------------------------------------
    allowed_actions = fields.Char(
        string="Allowed Actions",
        compute="_compute_allowed_actions",
        store=False,
        help="Comma-separated action names based on the current state.",
    )

    def get_allowed_actions(self):
        self.ensure_one()

        if self.state in self._TERMINAL_STATES:
            return []

        has_driver = bool(self._get_effective_driver_partner())

        if self.state in ("draft",):
            return ["set_waiting", "cancel"]
        if self.state in ("pending",):
            return ["assign" if has_driver else "set_waiting", "cancel"]
        if self.state in ("waiting",):
            actions = []
            if has_driver:
                actions.append("assign")
                actions.append("enroute")
            actions += ["cancel", "fail"]
            return actions
        if self.state in ("assigned",):
            return ["enroute", "cancel", "fail"]
        if self.state in ("enroute",):
            return ["deliver", "fail", "cancel"]

        return []

    @api.depends("state", "driver_id", "vehicle_id")
    def _compute_allowed_actions(self):
        for rec in self:
            rec.allowed_actions = ",".join(rec.get_allowed_actions())

    # -------------------------------------------------------------------------
    # SEQUENCE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        fixed_vals_list = []
        for vals in vals_list:
            if vals.get("name") in (False, None, "", "New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("meera.dispatch.order") or "New"

            vals = self._ensure_driver_from_vehicle_vals(vals)
            fixed_vals_list.append(vals)

        recs = super().create(fixed_vals_list)

        try:
            recs.action_sync_from_pos()
        except Exception:
            _logger.exception("[meera_dispatch] post-create sync_from_pos failed")
        return recs

    # -------------------------------------------------------------------------
    # POS SYNC (SELF-HEAL)
    # -------------------------------------------------------------------------
    def _is_empty_value(self, v):
        return v in (False, None, "", 0, 0.0)

    def action_sync_from_pos(self):
        """
        Sync dispatch fields from pos.order.
        This is where we map your meera_pos_order_type fields authoritatively.
        """
        for d in self:
            o = d.pos_order_id
            if not o:
                continue

            p = o.partner_id
            vals = {}

            if not d.partner_id and p:
                vals["partner_id"] = p.id

            if self._is_empty_value(d.customer_phone):
                phone = getattr(o, "delivery_phone", False) or (p.mobile or p.phone if p else False)
                if phone:
                    vals["customer_phone"] = str(phone).strip()

            if self._is_empty_value(d.delivery_address):
                addr = getattr(o, "delivery_address", False) or (p.contact_address if p else False)
                if addr:
                    vals["delivery_address"] = str(addr).strip()

            if self._is_empty_value(d.delivery_note):
                note = getattr(o, "delivery_note", False)
                if note:
                    vals["delivery_note"] = str(note).strip()

            if getattr(o, "is_delivery", False):
                vals["order_type"] = "delivery"
            elif getattr(o, "is_dine_in", False):
                vals["order_type"] = "dine_in"
            elif getattr(o, "is_takeaway", False):
                vals["order_type"] = "takeaway"

            vals = {k: v for k, v in vals.items() if k in d._fields and not self._is_empty_value(v)}
            if vals:
                d.sudo().write(vals)

        return True

    # -------------------------------------------------------------------------
    # HARDENED WRITE + AUTO-ASSIGN
    # -------------------------------------------------------------------------
    def write(self, vals):
        if "dispatch_state" in vals and "state" not in vals:
            vals["state"] = vals.get("dispatch_state")

        vals = self._ensure_driver_from_vehicle_vals(dict(vals or {}))

        skip_guard = self.env.context.get("meera_skip_state_guard")
        skip_auto_assign = self.env.context.get("meera_skip_auto_assign")

        new_state = vals.get("state") if "state" in vals else None

        if (new_state is not None) and (not skip_guard):
            for rec in self:
                old_state = rec.state or "waiting"
                if old_state in self._TERMINAL_STATES:
                    raise UserError(_("This dispatch job is already closed (%s).") % old_state)
                self._validate_state_transition(old_state, new_state)

        driver_being_set = ("driver_id" in vals and vals.get("driver_id"))
        vehicle_being_set = ("vehicle_id" in vals and vals.get("vehicle_id"))
        explicit_state_set = ("state" in vals) or ("dispatch_state" in vals)

        res = super().write(vals)

        if (not skip_auto_assign) and (not explicit_state_set) and (driver_being_set or vehicle_being_set):
            to_assign = self.filtered(lambda r: r.state in ("waiting", "pending", "draft"))
            for rec in to_assign:
                if rec._get_effective_driver_partner():
                    rec.with_context(meera_skip_auto_assign=True).write({"state": "assigned"})

        return res

    # -------------------------------------------------------------------------
    # ACTIONS (UI BUTTONS)
    # -------------------------------------------------------------------------
    def action_set_to_draft(self):
        return self.with_context(meera_skip_state_guard=True).write({"state": "draft"})

    def action_assign(self):
        self.write({"state": "assigned"})
        return True

    def action_enroute(self):
        self.write({"state": "enroute"})
        return True

    def action_delivered(self):
        self.write({"state": "delivered"})
        return True

    def action_failed(self):
        self.write({"state": "failed"})
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    # Backward-compatible aliases
    def action_reset_to_draft(self):
        return self.action_set_to_draft()

    def action_mark_enroute(self):
        return self.action_enroute()

    def action_mark_delivered(self):
        return self.action_delivered()

    def action_mark_failed(self):
        return self.action_failed()

    def action_mark_cancel(self):
        return self.action_cancel()
