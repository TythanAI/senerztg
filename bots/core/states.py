"""Finite-state-machine states used across the bot."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Checkout(StatesGroup):
    """Delivery-details collection for physical orders."""
    name = State()
    phone = State()
    address = State()
    comment = State()


class AdminFSM(StatesGroup):
    add_stock_pick = State()   # waiting for admin to send payloads
    broadcast = State()        # waiting for broadcast text


class SupportFSM(StatesGroup):
    message = State()          # waiting for the user's question to support
