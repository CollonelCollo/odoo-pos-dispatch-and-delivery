/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { rpc } from "@web/core/network/rpc";

/**
 * After the order is validated/synced, fetch the backend dispatch reference
 * (pos.order.meera_dispatch_reference) and store it on the frontend order.
 *
 * This is required because dispatch jobs are created on the backend (Python),
 * not from the POS frontend JS.
 */
patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const res = await super.validateOrder(...arguments);

        try {
            const order = this.pos.get_order?.();
            if (!order) return res;

            // If already set, don't refetch
            if (order.meera_dispatch_reference) return res;

            // In Odoo POS, server_id is present after sync
            const serverId = order.server_id || order.backendId;
            if (!serverId) return res;

            const recs = await rpc("/web/dataset/call_kw", {
                model: "pos.order",
                method: "read",
                args: [[serverId], ["meera_dispatch_reference"]],
                kwargs: {},
            });

            const ref = Array.isArray(recs) && recs[0] ? (recs[0].meera_dispatch_reference || "") : "";
            if (ref) {
                order.meera_dispatch_reference = ref;
                // keep this too, since our receipt exporter also checks it
                order.meera_dispatch_order_name = ref;
            }
        } catch (e) {
            console.warn("Meera POS: Failed to fetch dispatch reference after validation", e);
        }

        return res;
    },
});
