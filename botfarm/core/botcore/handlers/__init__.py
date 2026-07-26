"""Router assembly. Order matters — greedy text handlers must come last."""

from __future__ import annotations

from aiogram import Router

from . import admin, balance, catalog, checkout, common, profile, support


_BUILT = False


def build_router(modules: tuple[str, ...] = ()) -> Router:
    """Compose the routers this bot's niche actually needs.

    Call this once per process. The per-feature routers are module-level
    singletons, and aiogram lets a router have only one parent — which is
    exactly right for the deployment model here (one systemd unit or one
    container per bot) but means a single process cannot host two bots.
    """
    global _BUILT
    if _BUILT:
        raise RuntimeError(
            "build_router() was already called in this process. Each bot runs "
            "in its own process — see docs/DEPLOY.md. To host several bots at "
            "once, start one process per bot rather than reusing this one."
        )
    _BUILT = True

    root = Router(name="root")

    # Commands and callbacks first: they are all exact-match filters.
    root.include_router(common.router)
    root.include_router(admin.router)
    root.include_router(profile.router)
    root.include_router(checkout.router)

    if "balance" in modules:
        root.include_router(balance.router)

    if any(m in modules for m in ("support", "booking", "quiz", "leadgen")):
        root.include_router(support.router)

    # Last: catalog owns a loose `F.text` filter for bare promo codes.
    root.include_router(catalog.router)
    return root


__all__ = [
    "build_router",
    "admin",
    "balance",
    "catalog",
    "checkout",
    "common",
    "profile",
    "support",
]
