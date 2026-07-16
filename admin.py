"""
admin.py
========
Everything related to the admin panel: changing an order's status via
inline buttons, asking for a tracking code when an order is marked as
"Sent", and notifying the customer whenever their order status changes.

Only user ids listed in ``config.ADMIN_IDS`` are allowed to use these
handlers; everyone else's button presses are rejected with an alert.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import keyboards
from database import db, Order

logger = logging.getLogger(__name__)

# Single state: waiting for the admin to type the tracking code after
# pressing the "Sent" button.
ASK_TRACKING_CODE = 100

# context.user_data key (per-admin, not global) holding the order number
# currently being updated with a tracking code.
UD_PENDING_ORDER_NUMBER = "admin_pending_tracking_order_number"


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def _update_admin_message(update: Update, order: Order) -> None:
    """Refresh the admin's message so it reflects the new status."""
    query = update.callback_query
    new_caption = keyboards.format_order_for_admin(order) + (
        f"\n📌 وضعیت فعلی: {config.STATUS_LABELS.get(order.status, order.status)}"
    )
    keyboard = keyboards.admin_status_keyboard(order.order_number)
    try:
        if query.message.photo:
            await query.edit_message_caption(
                caption=new_caption, reply_markup=keyboard
            )
        else:
            await query.edit_message_text(text=new_caption, reply_markup=keyboard)
    except Exception:  # noqa: BLE001 - message may be unchanged, that's fine
        logger.debug("Could not edit admin message (probably unchanged).")


async def _notify_customer_status_change(
    context: ContextTypes.DEFAULT_TYPE, order: Order
) -> None:
    status_label = config.STATUS_LABELS.get(order.status, order.status)
    text = (
        f"📢 وضعیت سفارش شما به روز شد!\n\n"
        f"🧾 شماره سفارش: {order.order_number}\n"
        f"🛍 محصول: {order.product_name}\n"
        f"📌 وضعیت جدید: {status_label}\n"
    )
    if order.tracking_code:
        text += f"📮 کد رهگیری: {order.tracking_code}\n"

    try:
        await context.bot.send_message(chat_id=order.user_id, text=text)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to notify customer %s about order %s",
            order.user_id,
            order.order_number,
        )


async def handle_status_change(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point for every '<status button>' press in the admin panel."""
    query = update.callback_query
    admin_id = update.effective_user.id

    if not _is_admin(admin_id):
        await query.answer("شما اجازه دسترسی به این بخش را ندارید.", show_alert=True)
        return ConversationHandler.END

    await query.answer()

    try:
        _, order_number, new_status = query.data.split(":")
    except ValueError:
        await query.answer("داده نامعتبر است.", show_alert=True)
        return ConversationHandler.END

    order = db.get_order_by_number(order_number)
    if order is None:
        await query.answer("سفارش یافت نشد.", show_alert=True)
        return ConversationHandler.END

    if new_status == config.STATUS_SENT:
        # We need a tracking code before we can actually mark it as sent.
        context.user_data[UD_PENDING_ORDER_NUMBER] = order_number
        await query.message.reply_text(
            f"📮 لطفا کد رهگیری مرسوله سفارش {order_number} را وارد کنید:"
        )
        return ASK_TRACKING_CODE

    db.update_order_status(order_number, new_status)
    order = db.get_order_by_number(order_number)  # refreshed copy

    await _update_admin_message(update, order)
    await _notify_customer_status_change(context, order)

    return ConversationHandler.END


async def receive_tracking_code(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    admin_id = update.effective_user.id
    if not _is_admin(admin_id):
        return ConversationHandler.END

    order_number = context.user_data.get(UD_PENDING_ORDER_NUMBER)
    if not order_number:
        await update.message.reply_text(
            "خطا: سفارشی برای ثبت کد رهگیری یافت نشد."
        )
        return ConversationHandler.END

    tracking_code = (update.message.text or "").strip()
    if not tracking_code:
        await update.message.reply_text(
            "❗️ لطفا یک کد رهگیری معتبر وارد کنید."
        )
        return ASK_TRACKING_CODE

    db.set_tracking_code(order_number, tracking_code)
    order = db.get_order_by_number(order_number)

    await update.message.reply_text(
        f"✅ کد رهگیری برای سفارش {order_number} ثبت شد و وضعیت آن به "
        f"«{config.STATUS_LABELS[config.STATUS_SENT]}» تغییر کرد."
    )

    await _notify_customer_status_change(context, order)

    context.user_data.pop(UD_PENDING_ORDER_NUMBER, None)
    return ConversationHandler.END


async def cancel_admin_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    context.user_data.pop(UD_PENDING_ORDER_NUMBER, None)
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END


def build_admin_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_status_change, pattern=r"^status:"),
        ],
        states={
            ASK_TRACKING_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_tracking_code
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_admin_action),
        ],
        name="admin_status_conversation",
        persistent=False,
    )
