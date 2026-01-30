# -*- coding: utf-8 -*-
{
    "name": "POS Dispatch & Delivery (In-House Workflow)",
    "version": "18.0.1.0.0",
    "summary": "End-to-end dispatch & delivery workflow for POS orders with drivers, vehicles, and receipt integration.",
    "description": """
POS Dispatch & Delivery is a production-ready module for Odoo 18 that connects
Point of Sale orders with real-world delivery and dispatch operations.

The module automatically creates and manages dispatch jobs for delivery POS orders,
handles driver and vehicle assignment, and enhances POS receipts with delivery
and dispatch information such as Dispatch Reference, Order Type, and Delivery Details.

Key capabilities include:
- Automatic dispatch job creation for delivery POS orders
- One dispatch job per POS order (database-enforced)
- Full dispatch lifecycle management (Waiting, Assigned, En Route, Delivered, Failed, Cancelled)
- Backend-authoritative architecture (dispatch created server-side)
- POS receipt enhancements (Dispatch Reference, Order Type, Delivery Details)
- Clean OWL-safe POS extensions (Odoo 18 compliant)
- Offline-safe POS behavior with deferred sync support
- Driver and vehicle linking with optional live-location hooks
- Cron jobs for backfilling and self-healing missing dispatch records

Designed for restaurants, retail, and wholesale businesses running in-house or assigned deliveries.
""",
    "category": "Point of Sale",
    "author": "Dakill Technologies Ltd",
    "website": "https://github.com/CollonelCollo/odoo-18-pos-dispatch-and-delivery",
    "license": "OPL-1",
    "depends": [
        "mail",
        "point_of_sale",
        "fleet",
    ],
    "data": [
        # SECURITY (ALWAYS FIRST)
        "security/dispatch_security.xml",
        "security/ir.model.access.csv",
        "security/dispatch_rules.xml",

        # DATA
        "data/dispatch_sequence.xml",

        # VIEWS
        "views/dispatch_order_views.xml",
        "views/pos_order_views.xml",
        "views/pos_order_type_views.xml",
        "views/pos_config_views.xml",
        "views/fleet_vehicle_views.xml",
        "views/res_partner_views.xml",
        "views/driver_location_views.xml",

        # MENUS (TOP-LEVEL APP MENU)
        "views/dispatch_menus.xml",

        # CRON
        "data/dispatch_sync_cron.xml",
    ],
    "assets": {
        # Odoo 18 POS bundle
        "point_of_sale._assets_pos": [
            # POS data store
            "odoo_pos_dispatch/static/src/app/store/pos_order_type_data.js",

            # POS order model patches
            "odoo_pos_dispatch/static/src/app/models/pos_order_extensions.js",

            # POS logic
            "odoo_pos_dispatch/static/src/js/pos_order_type.js",
            "odoo_pos_dispatch/static/src/js/payment_guard.js",
            "odoo_pos_dispatch/static/src/js/pos_receipt_extend.js",
            "odoo_pos_dispatch/static/src/js/dispatch_reference_fetch.js",

            # POS templates
            "odoo_pos_dispatch/static/src/xml/pos_order_type_templates.xml",
            "odoo_pos_dispatch/static/src/xml/pos_receipt_templates.xml",
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/screenshots/01.png",
        "static/description/screenshots/02.png",
        "static/description/screenshots/03.png",
    ],
    "installable": True,
    "application": True,
}
