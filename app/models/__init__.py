"""
Import all models here so SQLAlchemy can resolve all relationships
regardless of which module is imported first.

This file is imported by app/db/session.py at startup, guaranteeing
every model is registered with Base.metadata before any query runs.
"""

from app.models.base import BaseModel  # noqa: F401
from app.models.budget import Budget  # noqa: F401
from app.models.budget_entry import BudgetEntry  # noqa: F401
from app.models.dish import Dish  # noqa: F401
from app.models.gathering import Gathering  # noqa: F401
from app.models.guest_rsvp import GuestRSVP  # noqa: F401
from app.models.menu import Menu  # noqa: F401
from app.models.prep_task import PrepTask  # noqa: F401
from app.models.recipe import Recipe  # noqa: F401
from app.models.reminder import Reminder  # noqa: F401
from app.models.shopping_item import ShoppingItem  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "BaseModel",
    "User",
    "Gathering",
    "GuestRSVP",
    "Menu",
    "Dish",
    "Recipe",
    "ShoppingItem",
    "PrepTask",
    "Budget",
    "BudgetEntry",
    "Reminder",
]
