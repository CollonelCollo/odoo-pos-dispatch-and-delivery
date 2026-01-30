# POS Dispatch & Delivery for Odoo 18

A production-ready **in-house dispatch & delivery workflow** for Odoo POS.

This module adds a structured, backend-authoritative dispatch layer on top of Odoo POS, allowing businesses to manage drivers, vehicles, delivery states, and receipt-level delivery information — without turning Odoo into a courier marketplace.

Built and battle-tested on **Odoo 18 Enterprise**.

---

## What This Module Does

- Creates **dispatch jobs** linked to POS orders
- Manages **delivery lifecycle states** (Waiting → Assigned → En Route → Delivered)
- Assigns **drivers and vehicles**
- Enhances **POS receipts** with delivery details
- Supports **offline POS workflows** safely
- Exposes a **lightweight driver API** for mobile apps or integrations

Designed for **restaurants, retail, and wholesale businesses** handling their own or assigned deliveries.

---

## What This Module Is NOT

To avoid confusion, this module is **not**:

- A multi-vendor courier marketplace
- A Glovo / Uber / Bolt-style delivery platform
- A route optimization or ETA engine
- A fully automated driver assignment AI

If you are building a courier SaaS or on-demand logistics platform, this module is not a fit.

---

## Key Features

### Dispatch Job Automation
- Automatic dispatch job creation for eligible POS orders
- Database-enforced **one dispatch job per POS order**
- Safe relink logic if a dispatch already exists

### Hardened Delivery States
- Waiting → Assigned → En Route → Delivered
- Failed / Cancelled terminal states
- Guarded transitions to prevent invalid operations

### POS Receipt Enhancements
- Dispatch reference printed on receipt (e.g. `DSP/00009`)
- Order type printed (Delivery / Takeaway / Dine-In)
- Delivery details (name, phone, address, note)

### Backend-Authoritative & Offline-Safe
- Server-side sequencing and reference generation
- POS fetches dispatch reference after successful sync
- Works with offline POS and deferred order sync

### Driver & Vehicle Tracking
- Assign drivers and vehicles to dispatch jobs
- Store last known vehicle location
- Open delivery and live vehicle maps from dispatch records

---

## Supported Odoo Versions

- **Odoo 18 Enterprise**
- Not tested on Community edition
- Not backward compatible with Odoo 16 or earlier

---

## Installation

1. Copy the module into your custom addons path:
   ```bash
   custom_addons/odoo_pos_dispatch
   ```

2. Update Apps List
3. Install **POS Dispatch & Delivery**
4. Reload POS once with:
   ```
   ?debug=assets
   ```

No core files are overwritten.

---

## Technical Notes

- Extends Odoo POS using safe asset additions
- OWL-compatible templates
- Backend-driven dispatch logic for multi-session correctness
- Designed for production stability, not demos

---

## License

LGPL-3

---

## Author

**Dakill Technologies Ltd**
Email: odhiambo.cedrick.dakill@gmail.com

Commercial support and customization available on request.
