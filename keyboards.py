"""
keyboards.py
============
All keyboard builders (ReplyKeyboardMarkup & InlineKeyboardMarkup) live
here so handlers.py / admin.py stay focused on business logic.
"""

from __future__ import annotations

from typing import List

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import config
from database import Order


# ---------------------------------------------------------------------------
# Reply keyboards
# ---------------------------------------------------------------------------


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard shown after /start."""
    keyboard = [
        [KeyboardButton(config.BTN_NEW_ORDER)],
        [KeyboardButton(config.BTN_MY_ORDERS)],
        [KeyboardButton(config.BTN_SUPPORT), KeyboardButton(config.BTN_CHANNELS)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Simple keyboard shown during the purchase flow to allow bailing out."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(config.BTN_CANCEL)]], resize_keyboard=True
    )


def phone_request_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with a Telegram native 'share contact' button."""
    keyboard = [
        [KeyboardButton(config.BTN_SHARE_PHONE, request_contact=True)],
        [KeyboardButton(config.BTN_CANCEL)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# ---------------------------------------------------------------------------
# Inline keyboards - shopping flow
# ---------------------------------------------------------------------------


def products_keyboard() -> InlineKeyboardMarkup:
    """List every product (active + inactive) as inline buttons."""
    rows: List[List[InlineKeyboardButton]] = []
    for product in config.PRODUCTS.values():
        prefix = "🟢" if product.active else "⚪️"
        label = f"{prefix} {product.name} - کد {product.code}"
        rows.append(
            [InlineKeyboardButton(label, callback_data=f"product:{product.code}")]
        )
    return InlineKeyboardMarkup(rows)


def models_keyboard(product_code: str) -> InlineKeyboardMarkup:
    product = config.PRODUCTS[product_code]
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for idx, model in enumerate(product.models, start=1):
        row.append(
            InlineKeyboardButton(
                model, callback_data=f"model:{product_code}:{idx - 1}"
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(config.BTN_BACK, callback_data="back_to_products")]
    )
    return InlineKeyboardMarkup(rows)


def confirm_order_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("✅ تایید و پرداخت", callback_data="confirm_order")],
        [InlineKeyboardButton(config.BTN_BACK, callback_data="back_to_products")],
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Inline keyboards - admin panel
# ---------------------------------------------------------------------------


def admin_status_keyboard(order_number: str) -> InlineKeyboardMarkup:
    """Inline buttons an admin uses to change an order's status."""
    rows = [
        [
            InlineKeyboardButton(
                config.STATUS_LABELS[config.STATUS_WAITING],
                callback_data=f"status:{order_number}:{config.STATUS_WAITING}",
            ),
            InlineKeyboardButton(
                config.STATUS_LABELS[config.STATUS_PREPARING],
                callback_data=f"status:{order_number}:{config.STATUS_PREPARING}",
            ),
        ],
        [
            InlineKeyboardButton(
                config.STATUS_LABELS[config.STATUS_SENT],
                callback_data=f"status:{order_number}:{config.STATUS_SENT}",
            ),
            InlineKeyboardButton(
                config.STATUS_LABELS[config.STATUS_DELIVERED],
                callback_data=f"status:{order_number}:{config.STATUS_DELIVERED}",
            ),
        ],
        [
            InlineKeyboardButton(
                config.STATUS_LABELS[config.STATUS_CANCELLED],
                callback_data=f"status:{order_number}:{config.STATUS_CANCELLED}",
            ),
        ],
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Text formatting helpers (not keyboards, but presentation-related, so they
# live next to the keyboard builders)
# ---------------------------------------------------------------------------


def format_order_summary(order: Order) -> str:
    tracking_line = (
        f"📮 کد رهگیری: {order.tracking_code}\n" if order.tracking_code else ""
    )
    return (
        f"🧾 شماره سفارش: {order.order_number}\n"
        f"🛍 محصول: {order.product_name} (کد {order.product_code})\n"
        f"🎨 مدل: {order.model}\n"
        f"🔢 تعداد: {order.quantity}\n"
        f"💰 قیمت واحد: {order.price_per_item:,} تومان\n"
        f"💵 مبلغ کل: {order.total_price:,} تومان\n"
        f"📅 تاریخ: {order.date}\n"
        f"📌 وضعیت: {config.STATUS_LABELS.get(order.status, order.status)}\n"
        f"{tracking_line}"
    )


def format_order_for_admin(order: Order) -> str:
    username_display = f"@{order.username}" if order.username else f"ID: {order.user_id}"
    return (
        "🆕 سفارش جدید\n\n"
        f"🧾 شماره سفارش: {order.order_number}\n"
        f"🛍 محصول: {order.product_name}\n"
        f"🔢 کد محصول: {order.product_code}\n"
        f"🎨 مدل: {order.model}\n"
        f"🔢 تعداد: {order.quantity}\n"
        f"💵 مبلغ کل: {order.total_price:,} تومان\n"
        f"👤 مشتری: {username_display}\n"
        f"🙍 نام کامل: {order.full_name}\n"
        f"📱 تلفن: {order.phone}\n"
        f"🏠 آدرس: {order.address}\n"
        f"📫 کدپستی: {order.postal_code}\n"
        f"📅 تاریخ: {order.date}\n"
    )
