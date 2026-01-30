# -*- coding: utf-8 -*-
import json
import logging

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _get_payload():
    """Read JSON payload from request (supports both proper JSON and raw body)."""
    try:
        data = request.httprequest.get_json(silent=True)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    try:
        raw = request.httprequest.get_data(cache=False, as_text=True) or ""
        raw = raw.strip()
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception:
        pass

    return {}


def _get_driver_token(payload):
    """Token priority: header X-Driver-Token, then payload.token."""
    headers = request.httprequest.headers
    token = headers.get("X-Driver-Token") or headers.get("x-driver-token")
    if token:
        return (token or "").strip()

    if isinstance(payload, dict):
        token = payload.get("token")
        if token:
            return (token or "").strip()

    return ""


def _resolve_partner_by_token(token):
    """
    Single source of truth:
      res.partner.meera_driver_token
    """
    Partner = request.env["res.partner"].sudo()
    if not token:
        return Partner.browse()

    if "meera_driver_token" not in Partner._fields:
        _logger.error("res.partner.meera_driver_token not found. Is odoo_pos_dispatch updated?")
        return Partner.browse()

    domain = [("meera_driver_token", "=", token)]
    if "meera_is_driver" in Partner._fields:
        domain.append(("meera_is_driver", "=", True))

    return Partner.search(domain, limit=1)


def _resolve_vehicle_by_token(token):
    """
    token -> res.partner (meera_driver_token) -> fleet.vehicle (dispatch_driver_id)
    """
    Vehicle = request.env["fleet.vehicle"].sudo()
    partner = _resolve_partner_by_token(token)
    if not partner:
        return Vehicle.browse()

    if "dispatch_driver_id" not in Vehicle._fields:
        _logger.error("fleet.vehicle.dispatch_driver_id not found. Is odoo_pos_dispatch updated?")
        return Vehicle.browse()

    domain = [("dispatch_driver_id", "=", partner.id)]
    if "is_dispatch_vehicle" in Vehicle._fields:
        domain.append(("is_dispatch_vehicle", "=", True))

    return Vehicle.search(domain, limit=1)


def _vehicle_driver_name(vehicle):
    drv = vehicle.dispatch_driver_id if "dispatch_driver_id" in vehicle._fields else False
    return (drv.name or "") if drv else ""


def _safe(rec, field_name, default=None):
    if field_name and field_name in rec._fields:
        return rec[field_name]
    return default


def _normalize_status(raw):
    """Normalize various client-side values into our known states."""
    s = (raw or "").strip().lower()
    if not s:
        return ""

    mapping = {
        "start": "enroute",
        "started": "enroute",
        "start_delivery": "enroute",
        "startdelivery": "enroute",
        "in_progress": "enroute",
        "inprogress": "enroute",
        "en_route": "enroute",
        "on_route": "enroute",
        "onroute": "enroute",
        "enroute": "enroute",

        "done": "delivered",
        "completed": "delivered",
        "complete": "delivered",
        "delivered": "delivered",

        "cancel": "cancelled",
        "cancelled": "cancelled",
        "canceled": "cancelled",

        "failed": "failed",
        "fail": "failed",

        "assigned": "assigned",
    }
    return mapping.get(s, s)


def _ensure_int(value):
    try:
        return int(value)
    except Exception:
        return None


def _json_ok(payload=None):
    """
    Legacy-friendly success envelope (many mobile clients rely on these exact keys).
    """
    body = {
        "success": True,
        "ok": True,
        "valid": True,
        "result": "ok",
        "status": "ok",
        "message": "ok",
        "code": 200,
        "error": None,
    }
    if isinstance(payload, dict):
        body.update(payload)
    return request.make_json_response(body)


def _json_err(code, extra=None):
    body = {
        "success": False,
        "ok": False,
        "valid": False,
        "result": "error",
        "status": "error",
        "error": code,
        "message": code,
        "code": 200,  # keep 200 for clients that hard-fail on non-200
    }
    if extra and isinstance(extra, dict):
        body.update(extra)
    return request.make_json_response(body)


def _build_order_payload(dispatch_order):
    """
    Build one order object in EXACTLY the same shape used by /meera/driver/orders.
    This makes it possible for the app to update UI instantly using the update response.
    """
    DispatchOrder = request.env["meera.dispatch.order"].sudo()
    pos_order_field = "pos_order_id" if "pos_order_id" in DispatchOrder._fields else None
    state_field = "state" if "state" in DispatchOrder._fields else ("status" if "status" in DispatchOrder._fields else None)

    addr_field = (
        "delivery_address_text" if "delivery_address_text" in DispatchOrder._fields else
        ("delivery_address" if "delivery_address" in DispatchOrder._fields else
         ("address" if "address" in DispatchOrder._fields else None))
    )

    o = dispatch_order
    partner = o.partner_id if "partner_id" in o._fields else request.env["res.partner"].sudo().browse()

    pos_ref = ""
    pos_name = ""
    amount_total = 0.0
    currency_symbol = ""

    po = o[pos_order_field] if (pos_order_field and pos_order_field in o._fields) else False
    if po:
        pos_ref = po.name or ""
        if "config_id" in po._fields and po.config_id:
            pos_name = po.config_id.name or ""
        if "amount_total" in po._fields:
            amount_total = float(po.amount_total or 0.0)
        if "currency_id" in po._fields and po.currency_id:
            currency_symbol = po.currency_id.symbol or ""

    addr = (_safe(o, addr_field, "") or "").strip()
    status_val = (_safe(o, state_field, "") or "").strip()
    status_norm = _normalize_status(status_val) or status_val

    lat = None
    lon = None

    oid = int(o.id)

    return {
        "id": oid,
        "order_id": oid,
        "orderId": oid,

        "name": getattr(o, "name", "") or "",
        "reference": getattr(o, "name", "") or "",

        "status": status_norm,
        "state": status_norm,
        "raw_status": status_val,

        "customer": (partner.name or "") if partner else "",
        "customer_name": (partner.name or "") if partner else "",
        "phone": (partner.phone or partner.mobile or "") if partner else "",
        "customer_phone": (partner.phone or partner.mobile or "") if partner else "",

        "pos": pos_name or "",
        "pos_name": pos_name or "",
        "pos_reference": pos_ref or "",
        "pos_order": pos_ref or "",

        "amount_total": amount_total,
        "amount": amount_total,

        "currency": currency_symbol or "",
        "currency_symbol": currency_symbol or "",

        "delivery_address": addr or "",
        "delivery_address_text": addr or "",
        "address": addr or "",

        "lat": lat,
        "lon": lon,
        "latitude": lat,
        "longitude": lon,
    }


def _fetch_open_orders_for_vehicle(vehicle):
    """
    Return open orders list in the same shape as /orders.
    """
    DispatchOrder = request.env["meera.dispatch.order"].sudo()
    vehicle_field = "vehicle_id" if "vehicle_id" in DispatchOrder._fields else None
    state_field = "state" if "state" in DispatchOrder._fields else ("status" if "status" in DispatchOrder._fields else None)

    if not vehicle_field:
        return []

    domain = [(vehicle_field, "=", vehicle.id)]
    if state_field:
        domain += [(state_field, "not in", ["done", "delivered", "cancel", "cancelled", "canceled", "failed"])]

    orders = DispatchOrder.search(domain, order="id desc", limit=200)
    return [_build_order_payload(o) for o in orders]


# -------------------------------------------------------------------------
# Controller
# -------------------------------------------------------------------------
class MeeraDriverApi(http.Controller):

    # ---------------------------------------------------------------------
    # 1) Fetch orders
    # ---------------------------------------------------------------------
    @http.route("/meera/driver/orders", type="http", auth="public", csrf=False, methods=["POST"])
    def driver_orders(self, **kwargs):
        payload = _get_payload()
        token = _get_driver_token(payload)

        if not token:
            return _json_err("missing_token")

        vehicle = _resolve_vehicle_by_token(token)
        if not vehicle:
            return _json_err("invalid_token")

        result = _fetch_open_orders_for_vehicle(vehicle)

        vehicle_name = vehicle.display_name or vehicle.name or ""
        driver_name = _vehicle_driver_name(vehicle) or ""

        # IMPORTANT: Keep data/results as LIST (legacy app expects JSONArray)
        return _json_ok({
            "count": len(result),
            "open": len(result),
            "vehicle": vehicle_name,
            "driver": driver_name,
            "orders": result,
            "data": result,      # alias list
            "results": result,   # alias list
        })

    # ---------------------------------------------------------------------
    # 2) Update order state
    # ---------------------------------------------------------------------
    @http.route("/meera/driver/update_order_status", type="http", auth="public", csrf=False, methods=["POST"])
    def update_order_status(self, **kwargs):
        payload = _get_payload()
        token = _get_driver_token(payload)

        if not token:
            return _json_err("missing_token")

        vehicle = _resolve_vehicle_by_token(token)
        if not vehicle:
            return _json_err("invalid_token")

        order_id = payload.get("order_id") or payload.get("orderId") or payload.get("id")
        raw_status = (
            payload.get("status")
            or payload.get("state")
            or payload.get("new_state")
            or payload.get("newState")
            or payload.get("action")
            or ""
        )

        order_id_int = _ensure_int(order_id)
        if not order_id_int:
            return _json_err("missing_or_invalid_order_id", extra={"received": order_id})

        new_status = _normalize_status(raw_status)

        allowed = {"assigned", "enroute", "delivered", "failed", "cancelled"}
        if new_status not in allowed:
            return _json_err("invalid_status", extra={
                "allowed": sorted(list(allowed)),
                "received": raw_status,
                "normalized": new_status,
            })

        DispatchOrder = request.env["meera.dispatch.order"].sudo()

        vehicle_field = "vehicle_id" if "vehicle_id" in DispatchOrder._fields else None
        state_field = "state" if "state" in DispatchOrder._fields else ("status" if "status" in DispatchOrder._fields else None)

        if not vehicle_field:
            return _json_err("dispatch_model_missing_vehicle_field")
        if not state_field:
            return _json_err("dispatch_model_missing_state_field")

        order = DispatchOrder.search([("id", "=", order_id_int), (vehicle_field, "=", vehicle.id)], limit=1)
        if not order:
            return _json_err("order_not_found_or_not_assigned", extra={"order_id": order_id_int, "vehicle_id": vehicle.id})

        before = (order[state_field] or "") if state_field in order._fields else ""
        order.write({state_field: new_status})
        order.flush_recordset([state_field])
        after = (order[state_field] or "") if state_field in order._fields else new_status

        _logger.info(
            "[MEERA DRIVER API] update_order_status token=%s vehicle=%s order=%s %s -> %s payload=%s",
            token[:6] + "***",
            vehicle.id,
            order.id,
            before,
            after,
            {k: payload.get(k) for k in ("order_id", "orderId", "id", "status", "state", "new_state", "newState", "action")},
        )

        oid = int(order.id)

        # Build the updated order object in the SAME SHAPE as /orders list item
        updated_order = _build_order_payload(order)

        # Also return the refreshed open list so clients can replace list without extra call
        open_orders = _fetch_open_orders_for_vehicle(vehicle)

        response_payload = {
            # Keep legacy fields
            "order_id": oid,
            "orderId": oid,
            "id": oid,
            "status": after,
            "state": after,
            "new_state": after,
            "newState": after,
            "updated": True,

            # NEW: strongly compatible fields for instant UI update
            "order": updated_order,
            "orders": open_orders,

            # keep these as list aliases (some clients use data/results for list replacement)
            "data": open_orders,
            "results": open_orders,

            "count": len(open_orders),
            "open": len(open_orders),
        }

        resp = _json_ok(response_payload)

        _logger.info(
            "[MEERA DRIVER API] update_order_status response order_id=%s orderId=%s id=%s state=%s open=%s",
            oid, oid, oid, after, len(open_orders)
        )

        return resp

    # ---------------------------------------------------------------------
    # 3) Send live location (driver tracking ONLY)
    # ---------------------------------------------------------------------
    @http.route("/meera/driver/update_location", type="http", auth="public", csrf=False, methods=["POST"])
    def update_location(self, **kwargs):
        payload = _get_payload()
        token = _get_driver_token(payload)

        if not token:
            return _json_err("missing_token")

        vehicle = _resolve_vehicle_by_token(token)
        if not vehicle:
            return _json_err("invalid_token")

        lat = payload.get("lat", payload.get("latitude"))
        lon = payload.get("lon", payload.get("longitude"))

        try:
            lat = float(lat)
            lon = float(lon)
        except Exception:
            return _json_err("invalid_lat_lon", extra={"received": {"lat": lat, "lon": lon}})

        vals = {}
        if "last_lat" in vehicle._fields:
            vals["last_lat"] = lat
        if "last_lng" in vehicle._fields:
            vals["last_lng"] = lon
        if "last_loc_time" in vehicle._fields:
            vals["last_loc_time"] = fields.Datetime.now()

        if vals:
            vehicle.sudo().write(vals)

        _logger.info(
            "[MEERA DRIVER API] update_location token=%s vehicle=%s lat=%.6f lon=%.6f",
            token[:6] + "***",
            vehicle.id,
            lat,
            lon,
        )

        return _json_ok({
            "lat": lat,
            "lon": lon,
            "latitude": lat,
            "longitude": lon,
            "data": {"lat": lat, "lon": lon, "latitude": lat, "longitude": lon},
            "results": {"lat": lat, "lon": lon, "latitude": lat, "longitude": lon},
        })
