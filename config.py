"""
config.py
=========
Central configuration for the Telegram shop bot.

All static/business configuration lives here so the rest of the codebase
never hard-codes business data (product list, prices, admin ids, etc).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Bot / Telegram settings
# ---------------------------------------------------------------------------

# It is strongly recommended to load the token from an environment variable
# instead of hard-coding it. If the env var is not set, replace the string
# below with your bot token before running.
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8938825588:AAFE-3WV1vdIMlOd6aNBu2T0XcNha87_VBM")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DB_NAME: str = os.getenv("BOT_DB_NAME", "shop.db")

# ---------------------------------------------------------------------------
# Admins
# ---------------------------------------------------------------------------

ADMIN_IDS: List[int] = [
    8218413228,
]

# ---------------------------------------------------------------------------
# Payment (Card to Card)
# ---------------------------------------------------------------------------

CARD_NUMBER: str = "6277601423137387"
CARD_OWNER: str = "زهرا شمشیری"

# ---------------------------------------------------------------------------
# Support / Channels
# ---------------------------------------------------------------------------

SUPPORT_CONTACTS: List[str] = [
    "@Aminfinisher",
]

CHANNELS: Dict[str, str] = {
    "Telegram": "https://t.me/TR_Art_Studio",
    "Rubika": "https://rubika.ir/TR_Art_Studio",
}

# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    price: int  # Toman
    active: bool
    models: List[str] = field(default_factory=list)


PRODUCTS: Dict[str, Product] = {
    "890": Product(
        code="890",
        name="روح های جنگلی شب تاب",
        price=89000,
        active=True,
        models=[f"مدل {i}" for i in range(1, 8)],  # Model 1 .. Model 7
    ),
    "990": Product(code="990", name="محصول 990", price=0, active=False),
    "110": Product(code="110", name="محصول 110", price=0, active=False),
    "870": Product(code="870", name="محصول 870", price=0, active=False),
    "650": Product(code="650", name="محصول 650", price=0, active=False),
    "115": Product(code="115", name="محصول 115", price=0, active=False),
    "417": Product(code="417", name="محصول 417", price=0, active=False),
}

INACTIVE_PRODUCT_MESSAGE: str = "❌ این محصول در حال حاضر موجود نیست."

# ---------------------------------------------------------------------------
# Order statuses
# ---------------------------------------------------------------------------

STATUS_WAITING = "waiting"
STATUS_PREPARING = "preparing"
STATUS_SENT = "sent"
STATUS_DELIVERED = "delivered"
STATUS_CANCELLED = "cancelled"

STATUS_LABELS: Dict[str, str] = {
    STATUS_WAITING: "🟡 در انتظار بررسی",
    STATUS_PREPARING: "🟠 در حال آماده سازی",
    STATUS_SENT: "🚚 ارسال شده",
    STATUS_DELIVERED: "✅ تحویل داده شده",
    STATUS_CANCELLED: "❌ لغو شده",
}

# ---------------------------------------------------------------------------
# Menu texts (used as ReplyKeyboard button labels and matched in handlers)
# ---------------------------------------------------------------------------

BTN_NEW_ORDER = "🛒 خرید محصول جدید"
BTN_MY_ORDERS = "📦 سفارش های من"
BTN_SUPPORT = "💬 پشتیبانی"
BTN_CHANNELS = "📢 کانال ها"
BTN_CANCEL = "❌ انصراف"
BTN_SHARE_PHONE = "📱 ارسال شماره تلفن"
BTN_CONFIRM = "✅ تایید و ادامه"
BTN_BACK = "🔙 بازگشت"
