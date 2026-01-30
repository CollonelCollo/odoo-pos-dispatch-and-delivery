# odoo_pos_dispatch/models/pos_order.py
# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    # ---------------------------------------------------------------------
    # ORDER TYPE + DELIVERY FIELDS
    # ---------------------------------------------------------------------

    order_type_id = fields.Many2one(
        "pos.order.type",
        string="Order Type",
        help="Meera Pizza order type (Dine-In, Take Away, Delivery).",
        compute="_compute_order_type",
        store=True,
        index=True,
    )

    is_delivery = fields.Boolean(string="Is Delivery", index=True)
    is_dine_in = fields.Boolean(string="Is Dine-In", index=True)
    is_takeaway = fields.Boolean(string="Is Takeaway", index=True)

    delivery_name = fields.Char(string="Delivery Customer Name")
    delivery_phone = fields.Char(string="Delivery Phone")
    delivery_address = fields.Text(string="Delivery Address")
    delivery_note = fields.Text(string="Delivery Note / Landmark")

    # ---------------------------------------------------------------------
    # DELIVERY COORDINATES (MERGED from meera_mobile_api)
    # ---------------------------------------------------------------------
    delivery_latitude = fields.Float(string="Delivery Latitude", digits=(16, 7))
    delivery_longitude = fields.Float(string="Delivery Longitude", digits=(16, 7))

    delivery_map_url = fields.Char(
        string="Delivery Map Link",
        compute="_compute_delivery_map_url",
        store=False,
    )

    @api.depends("delivery_latitude", "delivery_longitude")
    def _compute_delivery_map_url(self):
        for order in self:
            lat = order.delivery_latitude
            lng = order.delivery_longitude
            if lat and lng:
                order.delivery_map_url = (
                    "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=18/%s/%s"
                    % (lat, lng, lat, lng)
                )
            else:
                order.delivery_map_url = False

    def action_open_delivery_map(self):
        self.ensure_one()
        if not (self.delivery_latitude and self.delivery_longitude):
            raise UserError(_("No delivery coordinates set on this POS order."))
        return {
            "type": "ir.actions.act_url",
            "url": self.delivery_map_url,
            "target": "new",
        }

    # ---------------------------------------------------------------------
    # DISPATCH LINK
    # ---------------------------------------------------------------------

    dispatch_order_id = fields.Many2one(
        "meera.dispatch.order",
        string="Dispatch Job",
        copy=False,
        index=True,
        ondelete="set null",
        help="Created automatically for delivery orders once eligible.",
    )

    # ✅ THIS is what we will read from POS after sync and print on receipt
    meera_dispatch_reference = fields.Char(
        string="Dispatch Reference",
        related="dispatch_order_id.name",
        store=True,
        readonly=True,
        index=True,
    )

    dispatch_state = fields.Selection(
        related="dispatch_order_id.dispatch_state",
        string="Dispatch State",
        readonly=True,
        store=False,
    )

    # -------------------------------------------------------
    # UI smart button handler (your XML calls this)
    # -------------------------------------------------------
    def action_open_dispatch(self):
        self.ensure_one()
        if not self.dispatch_order_id:
            raise UserError(_("No dispatch job linked to this POS order."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Dispatch Job"),
            "res_model": "meera.dispatch.order",
            "view_mode": "form",
            "res_id": self.dispatch_order_id.id,
            "target": "current",
        }

    # ---------------------------------------------------------------------
    # POS UI -> BACKEND MAPPING
    # ---------------------------------------------------------------------
    @api.model
    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)

        extra = ui_order.get("meera_order_type") or {}

        is_delivery = extra.get("is_delivery", ui_order.get("is_delivery"))
        is_dine_in = extra.get("is_dine_in", ui_order.get("is_dine_in"))
        is_takeaway = extra.get("is_takeaway", ui_order.get("is_takeaway"))

        delivery_name = extra.get("delivery_name") or ui_order.get("delivery_name") or False
        delivery_phone = extra.get("delivery_phone") or ui_order.get("delivery_phone") or False
        delivery_address = extra.get("delivery_address") or ui_order.get("delivery_address") or False
        delivery_note = extra.get("delivery_note") or ui_order.get("delivery_note") or False

        # Coordinates (support multiple key names in UI payload just in case)
        delivery_latitude = (
            extra.get("delivery_latitude")
            or extra.get("delivery_lat")
            or ui_order.get("delivery_latitude")
            or ui_order.get("delivery_lat")
            or False
        )
        delivery_longitude = (
            extra.get("delivery_longitude")
            or extra.get("delivery_lng")
            or extra.get("delivery_long")
            or ui_order.get("delivery_longitude")
            or ui_order.get("delivery_lng")
            or ui_order.get("delivery_long")
            or False
        )

        # Normalize float if possible (avoid crashing on bad payload)
        try:
            delivery_latitude = float(delivery_latitude) if delivery_latitude not in (False, None, "", 0, 0.0) else False
        except Exception:
            delivery_latitude = False

        try:
            delivery_longitude = float(delivery_longitude) if delivery_longitude not in (False, None, "", 0, 0.0) else False
        except Exception:
            delivery_longitude = False

        vals.update(
            {
                "is_delivery": bool(is_delivery),
                "is_dine_in": bool(is_dine_in),
                "is_takeaway": bool(is_takeaway),
                "delivery_name": delivery_name,
                "delivery_phone": delivery_phone,
                "delivery_address": delivery_address,
                "delivery_note": delivery_note,
                "delivery_latitude": delivery_latitude,
                "delivery_longitude": delivery_longitude,
            }
        )
        return vals

    # ---------------------------------------------------------------------
    # Compute order_type_id anytime flags change
    # ---------------------------------------------------------------------
    @api.depends("is_delivery", "is_dine_in", "is_takeaway")
    def _compute_order_type(self):
        PosOrderType = self.env["pos.order.type"].sudo()

        for order in self:
            order_type = False

            if order.is_delivery:
                order_type = PosOrderType.search([("is_delivery", "=", True)], limit=1)
            elif order.is_dine_in:
                order_type = PosOrderType.search(
                    [("code", "in", ["DINE", "DINE-IN", "DINE_IN"])],
                    limit=1,
                )
            elif order.is_takeaway:
                order_type = PosOrderType.search(
                    [("code", "in", ["TAKE", "TAKEAWAY", "TAKE-AWAY"])],
                    limit=1,
                )

            order.order_type_id = order_type

    # -------------------------
    # Config helper
    # -------------------------
    @api.model
    def _meera_dispatch_create_before_payment(self):
        v = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("meera_dispatch.create_before_payment", default="1")
        )
        return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

    # -------------------------
    # Eligibility
    # -------------------------
    def _meera_dispatch_is_eligible(self):
        self.ensure_one()

        if not bool(getattr(self, "is_delivery", False)):
            return False

        allowed_states = ("paid", "done")
        if self._meera_dispatch_create_before_payment():
            allowed_states = ("draft", "paid", "done")

        if self.state not in allowed_states:
            return False

        # Optional: skip negative totals (refund-like)
        try:
            if self.amount_total is not None and self.amount_total < 0:
                return False
        except Exception:
            pass

        # Require phone + address (prevents useless jobs)
        if not (self.delivery_phone and self.delivery_address):
            return False

        return True

    # -------------------------
    # Extract payload
    # -------------------------
    def _meera_extract_dispatch_payload(self):
        self.ensure_one()

        partner = self.partner_id
        customer_id = partner.id if partner else False

        if self.delivery_phone:
            phone = str(self.delivery_phone).strip()
        elif partner:
            phone = (partner.mobile or partner.phone or "").strip() or False
        else:
            phone = False

        if self.delivery_address:
            delivery_address = str(self.delivery_address).strip()
        elif partner and getattr(partner, "contact_address", False):
            delivery_address = (partner.contact_address or "").strip() or False
        else:
            delivery_address = False

        company_partner = self.company_id.partner_id if self.company_id else False
        pickup_address = False
        if company_partner:
            pickup_address = (
                (company_partner.contact_address or company_partner.name or "").strip()
                or False
            )

        # Geo (optional)
        lat = None
        lng = None

        for f in ("delivery_latitude", "delivery_lat", "lat", "partner_latitude"):
            if hasattr(self, f):
                v = getattr(self, f)
                if v not in (None, False, 0, 0.0, "0", "0.0", ""):
                    try:
                        lat = float(v)
                        break
                    except Exception:
                        pass

        for f in ("delivery_longitude", "delivery_lng", "lng", "lon", "partner_longitude"):
            if hasattr(self, f):
                v = getattr(self, f)
                if v not in (None, False, 0, 0.0, "0", "0.0", ""):
                    try:
                        lng = float(v)
                        break
                    except Exception:
                        pass

        if lat is None and partner and getattr(partner, "partner_latitude", None):
            try:
                lat = float(partner.partner_latitude)
            except Exception:
                lat = None

        if lng is None and partner and getattr(partner, "partner_longitude", None):
            try:
                lng = float(partner.partner_longitude)
            except Exception:
                lng = None

        return {
            "customer_id": customer_id,
            "customer_phone": phone,
            "delivery_address": delivery_address,
            "pickup_address": pickup_address,
            "delivery_latitude": lat if lat is not None else False,
            "delivery_longitude": lng if lng is not None else False,
        }

    def _meera_sync_dispatch_fields(self):
        for order in self:
            job = order.dispatch_order_id
            if not job:
                continue

            payload = order._meera_extract_dispatch_payload()
            vals = {}

            for k, v in payload.items():
                if k not in job._fields:
                    continue
                current = job[k]
                is_missing = current in (False, None, "", 0, 0.0)
                has_value = v not in (False, None, "", 0, 0.0)
                if is_missing and has_value:
                    vals[k] = v

            if vals:
                job.sudo().write(vals)

    # -------------------------
    # Dispatch creation (DEDUPED)
    # -------------------------
    def _meera_ensure_dispatch_job(self):
        Dispatch = self.env["meera.dispatch.order"].sudo()

        for order in self:
            if not order._meera_dispatch_is_eligible():
                continue

            # 1) If already linked, just sync payload and move on
            if order.dispatch_order_id:
                order._meera_sync_dispatch_fields()
                continue

            # 2) HARD DEDUPE: search existing dispatch job by pos_order_id
            existing = Dispatch.search([("pos_order_id", "=", order.id)], limit=1)
            if existing:
                order.sudo().write({"dispatch_order_id": existing.id})
                order._meera_sync_dispatch_fields()
                _logger.info(
                    "[meera_dispatch] Re-linked existing dispatch job %s to POS order %s (%s)",
                    existing.id,
                    order.id,
                    order.pos_reference or order.name,
                )
                continue

            # 3) Create new dispatch job once
            vals = {
                "pos_order_id": order.id,
                "company_id": order.company_id.id if order.company_id else False,
            }

            payload = order._meera_extract_dispatch_payload()
            for k, v in payload.items():
                if k in Dispatch._fields:
                    vals[k] = v

            try:
                job = Dispatch.create(vals)
                order.sudo().write({"dispatch_order_id": job.id})
                order._meera_sync_dispatch_fields()

                _logger.info(
                    "[meera_dispatch] Created dispatch job %s for POS order %s (%s, total=%s, state=%s)",
                    job.id,
                    order.id,
                    order.pos_reference or order.name,
                    order.amount_total,
                    order.state,
                )
            except Exception:
                _logger.exception(
                    "[meera_dispatch] Failed creating dispatch for POS order %s (%s)",
                    order.id,
                    order.pos_reference or order.name,
                )

    # -------------------------
    # ORM hooks
    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._meera_ensure_dispatch_job()
        return orders

    def write(self, vals):
        res = super().write(vals)

        watched = {
            "state",
            "is_delivery",
            "is_dine_in",
            "is_takeaway",
            "partner_id",
            "delivery_name",
            "delivery_phone",
            "delivery_address",
            "delivery_note",
            "delivery_latitude",
            "delivery_longitude",
            "order_type_id",
        }
        if watched.intersection(vals.keys()):
            self._meera_ensure_dispatch_job()

        return res

    # -------------------------
    # Cron backfill
    # -------------------------
    @api.model
    def _cron_meera_backfill_missing_dispatch(self, limit=500):
        allowed_states = ("paid", "done")
        if self._meera_dispatch_create_before_payment():
            allowed_states = ("draft", "paid", "done")

        orders = self.search(
            [
                ("is_delivery", "=", True),
                ("state", "in", allowed_states),
                ("dispatch_order_id", "=", False),
                ("delivery_phone", "!=", False),
                ("delivery_address", "!=", False),
            ],
            order="id asc",
            limit=limit,
        )
        if orders:
            _logger.warning(
                "[meera_dispatch] Backfill: found %s delivery POS orders missing dispatch. Creating...",
                len(orders),
            )
            orders._meera_ensure_dispatch_job()
        return True

    @api.model
    def _cron_meera_backfill_dispatch_customer_fields(self, limit=1000):
        allowed_states = ("paid", "done")
        if self._meera_dispatch_create_before_payment():
            allowed_states = ("draft", "paid", "done")

        orders = self.search(
            [
                ("is_delivery", "=", True),
                ("state", "in", allowed_states),
                ("dispatch_order_id", "!=", False),
            ],
            order="id asc",
            limit=limit,
        )
        if orders:
            _logger.warning(
                "[meera_dispatch] Backfill: syncing customer/address fields for %s POS orders with dispatch.",
                len(orders),
            )
            orders._meera_sync_dispatch_fields()
        return True
