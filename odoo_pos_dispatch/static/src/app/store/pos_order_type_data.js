/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

console.log("Meera POS Order Type: store patch loaded");

/**
 * IMPORTANT:
 * - In a patch() object literal, `super` is NOT available.
 * - Capture the original method and call it with .call(this, ...).
 */
const _superProcessData = PosStore.prototype._processData;

patch(PosStore.prototype, {
    async _processData(loadedData) {
        // Let the standard POS loader run first
        if (_superProcessData) {
            await _superProcessData.call(this, loadedData);
        }

        // Use the data injected from pos.session._pos_ui_data()
        const orderTypes = loadedData["pos.order.type"] || [];

        console.log("Meera POS Order Type: loaded order types from UI data:", orderTypes);

        this.orderTypes = orderTypes;
        this.orderTypesById = {};

        for (const ot of orderTypes) {
            this.orderTypesById[ot.id] = ot;
        }
    },
});
