"""botcore — production engine shared by every bot in the farm.

A single bot is a thin package: a `config.yaml` (the niche) plus a `.env`
(the secrets). Everything else — payments, storefront, subscriptions,
referrals, admin, broadcasts — lives here and is exercised by the whole
fleet, so a fix lands in 300 products at once.
"""

__version__ = "1.4.0"

__all__ = ["__version__"]
