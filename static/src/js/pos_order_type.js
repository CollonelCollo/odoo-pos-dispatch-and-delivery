/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { rpc } from "@web/core/network/rpc";

/* =============================================================================
   MEERA POS ORDER TYPE (Odoo 18)
   - Adds Order Type selector popup
   - Handles Delivery details popup
   - Normalizes core `order.takeaway` to avoid crashes in pos_restaurant & core UI
   ========================================================================== */

/* ---------------------------------------------------------------------------
   0) Small utilities
--------------------------------------------------------------------------- */

const POPUP_ANIM_STYLE_ID = "popup-animations";
const OVERLAY_IDS = {
    orderType: "meera-order-type-overlay",
    delivery: "meera-delivery-details-overlay",
    guard: "meera-order-type-guard-popup",
};

function ensurePopupAnimations() {
    if (document.getElementById(POPUP_ANIM_STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = POPUP_ANIM_STYLE_ID;
    style.textContent = `
        @keyframes popupScaleIn {
            from { transform: scale(0.8); opacity: 0; }
            to   { transform: scale(1); opacity: 1; }
        }
    `;
    document.head.appendChild(style);
}

function removeById(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function safeUpper(s) {
    return String(s || "").trim().toUpperCase();
}

function pickPhone(partner) {
    return partner?.mobile || partner?.phone || "";
}

function partnerAddressString(partner) {
    if (!partner) return "";
    return [
        partner.street || "",
        partner.street2 || "",
        partner.city || "",
        partner.state_id?.[1] || "",
        partner.country_id?.[1] || "",
    ]
        .filter(Boolean)
        .join(", ");
}

/**
 * Core normalization:
 * Odoo restaurant flow expects `order.takeaway` boolean on the Order model.
 * Your module previously used only `order.is_takeaway`.
 * This setter enforces consistent state across:
 *  - core: order.takeaway (used by pos_restaurant)
 *  - custom: order.is_takeaway/is_dine_in/is_delivery + order_type_id/...
 */
function applyOrderTypeToOrder(order, orderType) {
    const code = safeUpper(orderType?.code);
    const isDelivery = !!orderType?.is_delivery;
    const isDine = code === "DINE";
    const isTake = code === "TAKE" || code === "TAKEAWAY";

    // Store selected type
    order.order_type_id = orderType?.id || null;
    order.order_type = orderType || null;
    order.order_type_code = code || null;

    // Custom flags (your module)
    order.is_delivery = isDelivery;
    order.is_dine_in = isDine;
    order.is_takeaway = isTake;

    // ✅ Core flag (pos_restaurant + core uses this)
    // Keep it always boolean
    order.takeaway = !!isTake;

    // Optional: if delivery, takeaway doesn't make sense; but keep as you decide.
    // If you want delivery to be treated as takeaway in core, uncomment:
    // if (isDelivery) order.takeaway = true;

    console.log("Meera POS: order type applied", {
        id: orderType?.id,
        name: orderType?.name,
        code,
        is_delivery: order.is_delivery,
        is_dine_in: order.is_dine_in,
        is_takeaway: order.is_takeaway,
        takeaway_core: order.takeaway,
    });
}

/* =============================================================================
   1) LIGHTWEIGHT POPUP HELPER (NO ODOO DEPENDENCIES)
   ============================================================================= */
function showGuardPopup(message, title = "Order Check", mode = "warning") {
    ensurePopupAnimations();
    removeById(OVERLAY_IDS.guard);

    const theme =
        {
            warning: { gradient: "linear-gradient(90deg, #ffb703, #fb8500)", icon: "⚠️" },
            error: { gradient: "linear-gradient(90deg, #e63946, #ff5f5f)", icon: "⛔" },
            info: { gradient: "linear-gradient(90deg, #6a11cb, #2575fc)", icon: "🔔" },
        }[mode] || { gradient: "linear-gradient(90deg, #6a11cb, #2575fc)", icon: "🔔" };

    const overlay = document.createElement("div");
    overlay.id = OVERLAY_IDS.guard;
    Object.assign(overlay.style, {
        position: "fixed",
        inset: "0",
        background: "rgba(0,0,0,0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: "50000",
        backdropFilter: "blur(2px)",
    });
    overlay.onclick = (ev) => {
        if (ev.target === overlay) overlay.remove();
    };

    const box = document.createElement("div");
    Object.assign(box.style, {
        width: "90%",
        maxWidth: "420px",
        background: "#fff",
        borderRadius: "14px",
        overflow: "hidden",
        boxShadow: "0 18px 40px rgba(0,0,0,0.35)",
        transform: "scale(0.8)",
        opacity: "0",
        animation: "popupScaleIn 0.18s forwards ease-out",
    });

    const header = document.createElement("div");
    Object.assign(header.style, {
        padding: "0.9rem 1.2rem",
        background: theme.gradient,
        color: "#fff",
        fontWeight: 600,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
    });

    const titleEl = document.createElement("span");
    titleEl.textContent = `${theme.icon} ${title}`;

    const closeBtn = document.createElement("button");
    closeBtn.innerHTML = "×";
    Object.assign(closeBtn.style, {
        background: "transparent",
        border: "none",
        color: "#fff",
        fontSize: "1.2rem",
        cursor: "pointer",
    });
    closeBtn.onclick = () => overlay.remove();

    header.append(titleEl, closeBtn);

    const body = document.createElement("div");
    Object.assign(body.style, {
        padding: "1.2rem",
        background: "#f8f9fa",
        fontSize: "0.9rem",
        color: "#333",
        whiteSpace: "pre-wrap",
    });
    body.textContent = message;

    const footer = document.createElement("div");
    Object.assign(footer.style, {
        padding: "0.85rem 1.2rem",
        display: "flex",
        justifyContent: "flex-end",
    });

    const okBtn = document.createElement("button");
    okBtn.textContent = "OK";
    Object.assign(okBtn.style, {
        background: theme.gradient,
        color: "#fff",
        border: "none",
        padding: "0.45rem 1.3rem",
        borderRadius: "20px",
        cursor: "pointer",
        fontSize: "0.85rem",
    });
    okBtn.onclick = () => overlay.remove();

    footer.appendChild(okBtn);
    box.append(header, body, footer);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    setTimeout(() => okBtn.focus(), 40);
}

/* =============================================================================
   2) DELIVERY DETAILS POPUP
   ============================================================================= */
function openDeliveryDetailsPopup(screen) {
    const pos = screen.pos;
    const order = pos.get_order?.();
    if (!order) return;

    removeById(OVERLAY_IDS.delivery);

    const overlay = document.createElement("div");
    overlay.id = OVERLAY_IDS.delivery;
    Object.assign(overlay.style, {
        position: "fixed",
        inset: "0",
        zIndex: "21000",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.35)",
        backdropFilter: "blur(2px)",
    });
    overlay.addEventListener("click", (ev) => {
        if (ev.target === overlay) overlay.remove();
    });

    const wrapper = document.createElement("div");
    Object.assign(wrapper.style, {
        position: "relative",
        minWidth: "420px",
        maxWidth: "580px",
        width: "90%",
    });

    const dialog = document.createElement("div");
    Object.assign(dialog.style, {
        background: "#ffffff",
        borderRadius: "12px",
        boxShadow: "0 14px 30px rgba(0,0,0,0.35)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
    });

    // Header
    const header = document.createElement("div");
    Object.assign(header.style, {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.9rem 1.3rem",
        borderBottom: "1px solid #e4e6ea",
        background: "linear-gradient(90deg, #a83279, #ff7b54)",
        color: "#fff",
    });

    const title = document.createElement("div");
    title.textContent = "Delivery Details";
    Object.assign(title.style, { fontSize: "1.05rem", fontWeight: "600" });

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.innerHTML = "✕";
    Object.assign(closeBtn.style, {
        border: "none",
        background: "transparent",
        color: "#fff",
        fontSize: "1rem",
        cursor: "pointer",
        padding: "0",
        marginLeft: "0.75rem",
    });
    closeBtn.addEventListener("click", () => overlay.remove());

    header.append(title, closeBtn);
    dialog.appendChild(header);

    // Body
    const body = document.createElement("div");
    Object.assign(body.style, { padding: "1rem 1.4rem 0.6rem 1.4rem", background: "#f7f8fa" });

    const helper = document.createElement("div");
    helper.textContent = "Confirm customer information and delivery address.";
    Object.assign(helper.style, {
        fontSize: "0.8rem",
        color: "#6c757d",
        marginBottom: "0.85rem",
    });
    body.appendChild(helper);

    const form = document.createElement("div");
    Object.assign(form.style, {
        display: "flex",
        flexDirection: "column",
        gap: "0.55rem",
    });

    function createField(labelText, placeholder, initialValue = "", isTextarea = false) {
        const group = document.createElement("div");
        Object.assign(group.style, { display: "flex", flexDirection: "column", gap: "0.15rem" });

        const label = document.createElement("label");
        label.textContent = labelText;
        Object.assign(label.style, {
            fontSize: "0.78rem",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            color: "#868e96",
        });

        const input = isTextarea ? document.createElement("textarea") : document.createElement("input");
        if (!isTextarea) input.type = "text";
        input.placeholder = placeholder;
        input.value = initialValue || "";
        Object.assign(input.style, {
            fontSize: "0.9rem",
            padding: "0.5rem 0.65rem",
            borderRadius: "8px",
            border: "1px solid #ced4da",
            outline: "none",
            resize: isTextarea ? "vertical" : "none",
            minHeight: isTextarea ? "60px" : "auto",
        });

        input.addEventListener("focus", () => {
            input.style.borderColor = "#a83279";
            input.style.boxShadow = "0 0 0 2px rgba(168,50,121,0.18)";
        });
        input.addEventListener("blur", () => {
            input.style.borderColor = "#ced4da";
            input.style.boxShadow = "none";
        });

        group.append(label, input);
        return { group, input };
    }

    const partner = order.get_partner ? order.get_partner() : order.partner;

    const partnerName = partner?.name || "";
    const partnerPhone = pickPhone(partner);
    const partnerAddress = partnerAddressString(partner);
    const partnerLandmark = partner?.x_meera_landmark || "";

    const nameField = createField("Customer Name", "Enter customer name", order.delivery_name || partnerName);
    const phoneField = createField("Phone Number", "e.g. 07xx xxx xxx", order.delivery_phone || partnerPhone);
    const addrField = createField("Delivery Address", "Street, building, floor", order.delivery_address || partnerAddress, true);
    const noteField = createField("Landmark / Notes (optional)", "Near XYZ building, gate color, etc.", order.delivery_note || partnerLandmark, true);

    form.append(nameField.group, phoneField.group, addrField.group, noteField.group);

    const errorBox = document.createElement("div");
    Object.assign(errorBox.style, {
        marginTop: "0.4rem",
        fontSize: "0.78rem",
        color: "#c92a2a",
        minHeight: "1em",
    });

    body.append(form, errorBox);
    dialog.appendChild(body);

    // Footer
    const footer = document.createElement("div");
    Object.assign(footer.style, {
        padding: "0.7rem 1.4rem 0.95rem 1.4rem",
        background: "#ffffff",
        borderTop: "1px solid #e4e6ea",
        display: "flex",
        justifyContent: "flex-end",
        gap: "0.55rem",
    });

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.textContent = "Cancel";
    Object.assign(cancelBtn.style, {
        borderRadius: "999px",
        border: "1px solid #ced4da",
        padding: "0.38rem 0.9rem",
        background: "#f8f9fa",
        fontSize: "0.85rem",
        cursor: "pointer",
    });
    cancelBtn.addEventListener("click", () => overlay.remove());

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = "Save & Continue";
    Object.assign(saveBtn.style, {
        borderRadius: "999px",
        border: "none",
        padding: "0.4rem 1.1rem",
        background: "linear-gradient(90deg, #a83279, #ff7b54)",
        color: "#fff",
        fontSize: "0.86rem",
        cursor: "pointer",
    });

    saveBtn.addEventListener("click", () => {
        const name = nameField.input.value.trim();
        const phone = phoneField.input.value.trim();
        const addr = addrField.input.value.trim();
        const note = noteField.input.value.trim();

        if (!phone || !addr) {
            errorBox.textContent = "Phone number and delivery address are required.";
            return;
        }

        order.delivery_name = name;
        order.delivery_phone = phone;
        order.delivery_address = addr;
        order.delivery_note = note;

        overlay.remove();
    });

    footer.append(cancelBtn, saveBtn);
    dialog.appendChild(footer);

    wrapper.appendChild(dialog);
    overlay.appendChild(wrapper);
    document.body.appendChild(overlay);
}

/* =============================================================================
   3) ORDER TYPE POPUP
   ============================================================================= */
function createOrderTypeOverlay(screen) {
    const pos = screen.pos;

    removeById(OVERLAY_IDS.orderType);

    const overlay = document.createElement("div");
    overlay.id = OVERLAY_IDS.orderType;
    Object.assign(overlay.style, {
        position: "fixed",
        inset: "0",
        zIndex: "20000",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0, 0, 0, 0.35)",
        backdropFilter: "blur(2px)",
    });
    overlay.addEventListener("click", (ev) => {
        if (ev.target === overlay) overlay.remove();
    });

    const wrapper = document.createElement("div");
    Object.assign(wrapper.style, {
        position: "relative",
        minWidth: "420px",
        maxWidth: "520px",
        width: "90%",
    });

    const dialog = document.createElement("div");
    Object.assign(dialog.style, {
        background: "#ffffff",
        borderRadius: "12px",
        boxShadow: "0 14px 30px rgba(0,0,0,0.35)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
    });

    // Header
    const header = document.createElement("div");
    Object.assign(header.style, {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.9rem 1.3rem",
        borderBottom: "1px solid #e4e6ea",
        background: "linear-gradient(90deg, #5e2ca5, #a83279)",
        color: "#fff",
    });

    const title = document.createElement("div");
    title.textContent = "Select Order Type";
    Object.assign(title.style, { fontSize: "1.05rem", fontWeight: "600" });

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.innerHTML = "✕";
    Object.assign(closeBtn.style, {
        border: "none",
        background: "transparent",
        color: "#fff",
        fontSize: "1rem",
        cursor: "pointer",
        padding: "0",
    });
    closeBtn.addEventListener("click", () => overlay.remove());

    header.append(title, closeBtn);
    dialog.appendChild(header);

    // Body
    const body = document.createElement("div");
    Object.assign(body.style, {
        padding: "0.9rem 1.3rem 0.3rem 1.3rem",
        background: "#f7f8fa",
    });

    const hint = document.createElement("div");
    hint.textContent = "Choose how this order should be handled.";
    Object.assign(hint.style, {
        fontSize: "0.8rem",
        color: "#6c757d",
        marginBottom: "0.6rem",
    });
    body.appendChild(hint);

    const listWrapper = document.createElement("div");
    Object.assign(listWrapper.style, {
        display: "flex",
        flexDirection: "column",
        gap: "0.45rem",
        marginBottom: "0.3rem",
    });

    const orderTypes = pos.orderTypes || [];

    if (!orderTypes.length) {
        const warn = document.createElement("div");
        warn.textContent = "No POS order types configured.";
        Object.assign(warn.style, {
            fontSize: "0.85rem",
            padding: "0.6rem 0.8rem",
            borderRadius: "6px",
            background: "#fff3cd",
            border: "1px solid #ffeeba",
            color: "#856404",
        });
        listWrapper.appendChild(warn);
    } else {
        for (const ot of orderTypes) {
            const btn = document.createElement("button");
            btn.type = "button";
            Object.assign(btn.style, {
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "0.65rem 0.85rem",
                borderRadius: "10px",
                border: "1px solid #dee2e6",
                background: "#ffffff",
                cursor: "pointer",
                fontSize: "0.9rem",
                transition: "all 0.12s ease-in-out",
                textAlign: "left",
            });

            btn.addEventListener("mouseenter", () => {
                btn.style.borderColor = "#a83279";
                btn.style.boxShadow = "0 0 0 2px rgba(168,50,121,0.18)";
            });
            btn.addEventListener("mouseleave", () => {
                btn.style.borderColor = "#dee2e6";
                btn.style.boxShadow = "none";
            });

            const left = document.createElement("div");
            const nameSpan = document.createElement("div");
            nameSpan.textContent = ot.name || "Order Type";
            Object.assign(nameSpan.style, { fontWeight: "600", color: "#343a40" });

            const meta = document.createElement("div");
            meta.textContent = ot.is_delivery ? "Delivery / Dispatch" : "In-store";
            Object.assign(meta.style, { fontSize: "0.75rem", color: "#868e96" });

            left.append(nameSpan, meta);

            const right = document.createElement("div");
            Object.assign(right.style, { display: "flex", alignItems: "center", gap: "0.45rem" });

            if (ot.code) {
                const codeBadge = document.createElement("span");
                codeBadge.textContent = ot.code;
                Object.assign(codeBadge.style, {
                    fontSize: "0.7rem",
                    padding: "0.15rem 0.55rem",
                    borderRadius: "999px",
                    background: "#f1f3f5",
                    color: "#495057",
                });
                right.appendChild(codeBadge);
            }

            const arrow = document.createElement("span");
            arrow.textContent = "➜";
            Object.assign(arrow.style, { fontSize: "0.9rem", color: "#a83279" });
            right.appendChild(arrow);

            btn.append(left, right);

            btn.addEventListener("click", () => {
                const order = pos.get_order?.();
                if (!order) return;

                applyOrderTypeToOrder(order, ot);
                overlay.remove();

                if (ot.is_delivery) {
                    const partner = order.get_partner ? order.get_partner() : order.partner;
                    if (!partner) {
                        showGuardPopup(
                            "Please select a customer first using the Customer button.",
                            "Customer Required",
                            "warning"
                        );
                        return;
                    }
                    openDeliveryDetailsPopup(screen);
                }
            });

            listWrapper.appendChild(btn);
        }
    }

    body.appendChild(listWrapper);
    dialog.appendChild(body);

    // Footer
    const footer = document.createElement("div");
    Object.assign(footer.style, {
        padding: "0.7rem 1.3rem 0.9rem 1.3rem",
        display: "flex",
        justifyContent: "flex-end",
        gap: "0.5rem",
        background: "#ffffff",
        borderTop: "1px solid #e4e6ea",
    });

    const closeBtn2 = document.createElement("button");
    closeBtn2.type = "button";
    closeBtn2.textContent = "Close";
    Object.assign(closeBtn2.style, {
        borderRadius: "999px",
        border: "1px solid #ced4da",
        padding: "0.35rem 0.9rem",
        background: "#f8f9fa",
        cursor: "pointer",
    });
    closeBtn2.addEventListener("click", () => overlay.remove());

    footer.appendChild(closeBtn2);
    dialog.appendChild(footer);

    wrapper.appendChild(dialog);
    overlay.appendChild(wrapper);
    document.body.appendChild(overlay);
}

/* =============================================================================
   4) Load Order Types once (cached)
   ============================================================================= */
async function ensureOrderTypesLoaded(pos) {
    if (Array.isArray(pos.orderTypes) && pos.orderTypes.length) return;

    try {
        const result = await rpc("/web/dataset/call_kw", {
            model: "pos.order.type",
            method: "search_read",
            args: [[]],
            kwargs: { fields: ["id", "name", "code", "is_delivery"] },
        });

        pos.orderTypes = Array.isArray(result) ? result : [];
        pos.orderTypesById = Object.fromEntries((pos.orderTypes || []).map((ot) => [ot.id, ot]));

        console.log("Meera POS: Loaded POS Order Types:", pos.orderTypes);
    } catch (e) {
        console.error("Meera POS: Error loading order types", e);
        pos.orderTypes = [];
        pos.orderTypesById = {};
    }
}

/* =============================================================================
   5) PATCH PRODUCT SCREEN BUTTON HANDLER
   ============================================================================= */
patch(ProductScreen.prototype, {
    async onClickOrderType() {
        // Prevent double taps opening multiple overlays
        if (this.__meeraOrderTypeBusy) return;
        this.__meeraOrderTypeBusy = true;

        try {
            const order = this.pos.get_order?.();
            if (!order) return;

            await ensureOrderTypesLoaded(this.pos);
            createOrderTypeOverlay(this);
        } finally {
            // small delay to avoid accidental double clicks
            setTimeout(() => (this.__meeraOrderTypeBusy = false), 250);
        }
    },
});
