"""Router assembly. Order matters — greedy text handlers must come last."""

from __future__ import annotations

from aiogram import Router

from . import admin, catalog, checkout, common, profile, support


def build_router(modules: tuple[str, ...] = ()) -> Router:
    """Compose the routers this bot's niche actually needs."""
    root = Router(name="root")

    # Commands and callbacks first: they are all exact-match filters.
    root.include_router(common.router)
    root.include_router(admin.router)
    root.include_router(profile.router)
    root.include_router(checkout.router)

    if any(m in modules for m in ("support", "booking", "quiz", "leadgen")):
        root.include_router(support.router)

    # Last: catalog owns a loose `F.text` filter for bare promo codes.
    root.include_router(catalog.router)
    return root


__all__ = ["build_router", "admin", "catalog", "checkout", "common", "profile", "support"]
