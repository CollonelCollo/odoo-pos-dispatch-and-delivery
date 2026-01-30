# -*- coding: utf-8 -*-
"""
Meera POS Dispatch - HTTP Controllers

Keep route names unique across the module.

We expose the Driver App endpoints via `driver_api.py`.
The legacy `driver_tracking.py` file previously duplicated the same routes
(`/meera/driver/*`) which caused route collisions and unpredictable behavior.

NOTE:
- Only controllers imported here are mounted by Odoo.
"""

from . import driver_api
