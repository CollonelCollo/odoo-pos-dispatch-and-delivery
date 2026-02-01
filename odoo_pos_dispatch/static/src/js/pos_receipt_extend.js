/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

/**
 * Odoo 18 - Receipt data injection (odoo_pos_dispatch)
 *
 * Our OWL template reads from props.data.* (headerData).
 */
patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments) || {};
        const data = result.headerData || (result.headerData = {});

        const setBoth = (key, value) => {
            data[key] = value;
            result[key] = value; // keep also on root for safety
        };

        // ------------------------------------------------------------
        // Dispatch Reference (meera.dispatch.order.name)
        // ------------------------------------------------------------
        // We read from the most likely fields where our dispatch logic stores it.
        // One of these SHOULD exist if dispatch order is created before payment.
        const dispatchRef =
            this.meera_dispatch_reference ||
            this.meera_dispatch_ref ||
            this.dispatch_reference ||
            this.dispatch_ref ||
            this.dispatch_order_name ||
            this.meera_dispatch_order_name ||
            (this.dispatch_order && this.dispatch_order.name) ||
            "";

        setBoth("meera_dispatch_reference", dispatchRef || "");

        // ------------------------------------------------------------
        // Customer details (partner)
        // ------------------------------------------------------------
        if (this.partner_id) {
            const partner = this.partner_id;

            setBoth("meera_customer_name", partner.name || "");
            setBoth("meera_customer_address", partner.contact_address || partner.street || "");
            setBoth("meera_customer_mobile", partner.mobile || "");
            setBoth("meera_customer_phone", partner.phone || "");
            setBoth("meera_customer_email", partner.email || "");
            setBoth("meera_customer_vat", partner.vat || "");
        } else {
            setBoth("meera_customer_name", "");
            setBoth("meera_customer_address", "");
            setBoth("meera_customer_mobile", "");
            setBoth("meera_customer_phone", "");
            setBoth("meera_customer_email", "");
            setBoth("meera_customer_vat", "");
        }

        // ------------------------------------------------------------
        // Order type name (robust)
        // ------------------------------------------------------------
        let orderTypeName = "";

        if (this.order_type_name) {
            orderTypeName = this.order_type_name;
        } else if (Array.isArray(this.order_type_id)) {
            orderTypeName = this.order_type_id[1] || "";
        } else if (this.order_type_id) {
            const pos = this.pos || this.env?.services?.pos;
            const byId = pos?.orderTypesById || {};
            const ot = byId[this.order_type_id];
            if (ot?.name) orderTypeName = ot.name;
        }

        // ------------------------------------------------------------
        // Detect delivery / takeaway / dine-in
        // ------------------------------------------------------------
        const isDelivery =
            !!this.is_delivery ||
            (orderTypeName && String(orderTypeName).toLowerCase().includes("delivery"));

        const isTakeaway =
            !!this.takeaway ||
            (orderTypeName && String(orderTypeName).toLowerCase().includes("takeaway"));

        const isDineIn = !!(this.table_id || this.table);

        if (!orderTypeName) {
            if (isDelivery) orderTypeName = "Delivery";
            else if (isTakeaway) orderTypeName = "Takeaway";
            else if (isDineIn) orderTypeName = "Dine In";
        }

        setBoth("meera_is_delivery", !!isDelivery);
        setBoth("meera_order_type_name", orderTypeName || "");

        // ------------------------------------------------------------
        // Delivery details
        // ------------------------------------------------------------
        if (isDelivery) {
            const partner = this.partner_id || null;

            const dName = this.delivery_name || partner?.name || "";
            const dPhone = this.delivery_phone || partner?.mobile || partner?.phone || "";
            const dAddress = this.delivery_address || partner?.contact_address || partner?.street || "";
            const dNote = this.delivery_note || "";

            setBoth("meera_delivery_name", dName);
            setBoth("meera_delivery_phone", dPhone);
            setBoth("meera_delivery_address", dAddress);
            setBoth("meera_delivery_note", dNote);
        } else {
            setBoth("meera_delivery_name", "");
            setBoth("meera_delivery_phone", "");
            setBoth("meera_delivery_address", "");
            setBoth("meera_delivery_note", "");
        }

        return result;
    },
});
