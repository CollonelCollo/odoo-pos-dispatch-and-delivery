/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

console.log("Meera POS: PosOrder import/export patch loaded");

/* ============================================================================
   Capture original implementations (Odoo version–agnostic)
   ========================================================================== */
const proto = PosOrder.prototype;

// Export
const _superExportSnake = proto.export_as_JSON;
const _superExportCamel = proto.exportAsJSON;
const _superExport = _superExportSnake || _superExportCamel;

// Import
const _superInitSnake = proto.init_from_JSON;
const _superInitCamel = proto.initFromJSON;
const _superInit = _superInitSnake || _superInitCamel;

/* ============================================================================
   Patch PosOrder
   ========================================================================== */
patch(PosOrder.prototype, {
    /* ------------------------------------------------------------------------
       EXPORT
       ---------------------------------------------------------------------- */
    export_as_JSON() {
        // Always start from core export
        const json = _superExport ? _superExport.call(this, ...arguments) : {};

        /* ---- Order type & flags (authoritative) ---- */
        json.order_type_id = this.order_type_id || false;
        json.order_type_code = this.order_type_code || null;

        json.is_delivery = !!this.is_delivery;
        json.is_dine_in = !!this.is_dine_in;
        json.is_takeaway = !!this.is_takeaway;

        // ✅ CORE FIELD (critical)
        json.takeaway = !!this.takeaway;

        /* ---- Delivery details ---- */
        json.delivery_name = this.delivery_name || "";
        json.delivery_phone = this.delivery_phone || "";
        json.delivery_address = this.delivery_address || "";
        json.delivery_note = this.delivery_note || "";

        /* ---- Nested Meera block (future-proof & Python-friendly) ---- */
        json.meera_order_type = {
            id: json.order_type_id,
            code: json.order_type_code,
            is_delivery: json.is_delivery,
            is_dine_in: json.is_dine_in,
            is_takeaway: json.is_takeaway,
            takeaway: json.takeaway,
            delivery_name: json.delivery_name,
            delivery_phone: json.delivery_phone,
            delivery_address: json.delivery_address,
            delivery_note: json.delivery_note,
        };

        return json;
    },

    // CamelCase alias safety
    exportAsJSON() {
        return this.export_as_JSON(...arguments);
    },

    /* ------------------------------------------------------------------------
       IMPORT
       ---------------------------------------------------------------------- */
    init_from_JSON(json) {
        if (_superInit) {
            _superInit.call(this, json);
        }

        /* ---- Restore order type ---- */
        this.order_type_id = json.order_type_id || false;
        this.order_type_code = json.order_type_code || null;

        this.is_delivery = !!json.is_delivery;
        this.is_dine_in = !!json.is_dine_in;
        this.is_takeaway = !!json.is_takeaway;

        // ✅ CORE FIELD (authoritative restore)
        this.takeaway =
            json.takeaway !== undefined
                ? !!json.takeaway
                : !!json.is_takeaway;

        /* ---- Restore delivery details ---- */
        this.delivery_name = json.delivery_name || "";
        this.delivery_phone = json.delivery_phone || "";
        this.delivery_address = json.delivery_address || "";
        this.delivery_note = json.delivery_note || "";

        /* ---- Backward compatibility (older dumps) ---- */
        if (json.meera_order_type) {
            const m = json.meera_order_type;
            this.is_delivery = !!m.is_delivery;
            this.is_dine_in = !!m.is_dine_in;
            this.is_takeaway = !!m.is_takeaway;
            this.takeaway = m.takeaway !== undefined ? !!m.takeaway : this.takeaway;

            this.delivery_name ||= m.delivery_name || "";
            this.delivery_phone ||= m.delivery_phone || "";
            this.delivery_address ||= m.delivery_address || "";
            this.delivery_note ||= m.delivery_note || "";
        }
    },

    // CamelCase alias safety
    initFromJSON(json) {
        return this.init_from_JSON(json);
    },
});
