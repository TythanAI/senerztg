"""Handler routers, assembled in the order they should be evaluated."""
from __future__ import annotations

from aiogram import Dispatcher

from . import admin, cart, catalog, checkout, common, payment, support


def setup_routers(dp: Dispatcher) -> None:
    # Admin first so its commands/filters win, then feature routers, then
    # the generic/support fallback last.
    dp.include_router(admin.router)
    dp.include_router(common.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)
    dp.include_router(payment.router)
    dp.include_router(support.router)
