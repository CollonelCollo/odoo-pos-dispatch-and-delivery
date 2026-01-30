/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/**
 * Smooth, modern popup (no Odoo popup imports)
 */
function showGuardPopup(message, title = "Order Check", mode = "warning") {
    const existing = document.getElementById("meera-payment-guard-popup");
    if (existing) {
        existing.remove();
    }

    // Themes
    const theme =
        {
            warning: {
                gradient: "linear-gradient(90deg, #ffb703, #fb8500)",
                icon: "⚠️",
            },
            error: {
                gradient: "linear-gradient(90deg, #e63946, #ff5f5f)",
                icon: "⛔",
            },
            delivery: {
                gradient: "linear-gradient(90deg, #a83279, #ff7b54)",
                icon: "🚚",
            },
        }[mode] || {
            gradient: "linear-gradient(90deg, #6a11cb, #2575fc)",
            icon: "🔔",
        };

    // Overlay
    const overlay = document.createElement("div");
    overlay.id = "meera-payment-guard-popup";
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

    // Popup container
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

    // Header
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
    titleEl.innerHTML = `${theme.icon} ${title}`;

    const closeBtn = document.createElement("button");
    closeBtn.innerHTML = "&times;";
    Object.assign(closeBtn.style, {
        background: "transparent",
        border: "none",
        color: "#fff",
        fontSize: "1.2rem",
        cursor: "pointer",
    });
    closeBtn.onclick = () => overlay.remove();

    header.append(titleEl, closeBtn);

    // Body
    const body = document.createElement("div");
    Object.assign(body.style, {
        padding: "1.2rem",
        background: "#f8f9fa",
        fontSize: "0.9rem",
        color: "#333",
        whiteSpace: "pre-wrap",
    });
    body.textContent = message;

    // Footer
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

    // Assemble
    box.append(header, body, footer);
    overlay.appendChild(box);
    document.body.appendChild(overlay);

    // Keyframe animation injection once
    if (!document.getElementById("popup-animations")) {
        const style = document.createElement("style");
        style.id = "popup-animations";
        style.textContent = `
            @keyframes popupScaleIn {
                from { transform: scale(0.8); opacity: 0; }
                to { transform: scale(1); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }

    setTimeout(() => okBtn.focus(), 40);
}

/**
 * Keep original PaymentScreen validate behavior
 */
const OriginalValidateOrder = PaymentScreen.prototype.validateOrder;

/**
 * Patch logic
 */
patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const order = this.pos.get_order();
        if (!order) {
            return OriginalValidateOrder.call(this, isForceValidate);
        }

        // Require Order Type
        if (!order.order_type_id && !order.order_type) {
            showGuardPopup(
                "Please select an Order Type before proceeding to payment.",
                "Order Check",
                "warning"
            );
            return;
        }

        // Delivery checks
        const isDelivery =
            order.is_delivery ||
            (order.order_type && order.order_type.is_delivery);

        if (isDelivery) {
            const missing = [];
            if (!order.delivery_phone?.trim()) missing.push("• Phone number");
            if (!order.delivery_address?.trim()) missing.push("• Delivery address");

            if (missing.length) {
                showGuardPopup(
                    "This is a Delivery order.\n\nMissing:\n" +
                        missing.join("\n"),
                    "Delivery Details Required",
                    "delivery"
                );
                return;
            }
        }

        return OriginalValidateOrder.call(this, isForceValidate);
    },
});
