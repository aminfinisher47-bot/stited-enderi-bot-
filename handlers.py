"""
handlers.py
===========
User-facing handlers: main menu, "my orders", support/channels buttons and
the full purchase ``ConversationHandler`` flow.

State is NEVER stored in module-level/global variables. Everything that
needs to persist between steps of a conversation is stored in
``context.user_data`` (per-chat, provided by python-telegram-bot itself),
which is the recommended, thread-safe way to keep per-user state.
"""

from __future__ import annotations

import logging
from typing import Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ParseMode
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
from database import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conversation states
# ---------------------------------------------------------------------------

(
    SELECT_PRODUCT,
    SELECT_MODEL,
    ASK_QUANTITY,
    CONFIRM_ORDER,
    WAIT_RECEIPT,
    ASK_NAME,
    ASK_PHONE,
    ASK_ADDRESS,
    ASK_POSTAL,
) = range(9)

# Keys used inside context.user_data while a purchase is in progress.
UD_PRODUCT_CODE = "purchase_product_code"
UD_MODEL = "purchase_model"
UD_QUANTITY = "purchase_quantity"
UD_RECEIPT_FILE_ID = "purchase_receipt_file_id"
UD_FULL_NAME = "purchase_full_name"
UD_PHONE = "purchase_phone"
UD_ADDRESS = "purchase_address"


def _clear_purchase_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in (
        UD_PRODUCT_CODE,
        UD_MODEL,
        UD_QUANTITY,
        UD_RECEIPT_FILE_ID,
        UD_FULL_NAME,
        UD_PHONE,
        UD_ADDRESS,
    ):
        context.user_data.pop(key, None)


# ---------------------------------------------------------------------------
# /start and main menu buttons
# ---------------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.upsert_user(user_id=user.id, username=user.username)
    await update.message.reply_text(
        f"سلام {user.first_name} 👋\n"
        "به فروشگاه ما خوش آمدید!\n\n"
        "از منوی زیر یکی از گزینه ها را انتخاب کنید:",
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contacts = "\n".join(config.SUPPORT_CONTACTS)
    await update.message.reply_text(
        f"💬 پشتیبانی\n\nبرای ارتباط با ما پیام دهید:\n{contacts}",
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def show_channels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"{name}: {url}" for name, url in config.CHANNELS.items()]
    await update.message.reply_text(
        "📢 کانال های ما\n\n" + "\n".join(lines),
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    orders = db.get_user_orders(user_id)
    if not orders:
        await update.message.reply_text(
            "📦 شما هنوز هیچ سفارشی ثبت نکرده اید.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    await update.message.reply_text(
        f"📦 سفارش های شما ({len(orders)} سفارش):",
        reply_markup=keyboards.main_menu_keyboard(),
    )
    for order in orders:
        await update.message.reply_text(keyboards.format_order_summary(order))


# ---------------------------------------------------------------------------
# Purchase flow - entry point
# ---------------------------------------------------------------------------


async def start_purchase(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    _clear_purchase_state(context)
    await update.message.reply_text(
        "🛍 لطفا یکی از محصولات زیر را انتخاب کنید:",
        reply_markup=keyboards.products_keyboard(),
    )
    return SELECT_PRODUCT


async def select_product(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    product_code = query.data.split(":", 1)[1]
    product = config.PRODUCTS.get(product_code)

    if product is None:
        await query.edit_message_text("محصول یافت نشد.")
        return ConversationHandler.END

    if not product.active:
        await query.answer(config.INACTIVE_PRODUCT_MESSAGE, show_alert=True)
        return SELECT_PRODUCT

    context.user_data[UD_PRODUCT_CODE] = product_code
    await query.edit_message_text(
        f"محصول انتخابی: {product.name}\n\nلطفا مدل مورد نظر را انتخاب کنید:",
        reply_markup=keyboards.models_keyboard(product_code),
    )
    return SELECT_MODEL


async def back_to_products(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🛍 لطفا یکی از محصولات زیر را انتخاب کنید:",
        reply_markup=keyboards.products_keyboard(),
    )
    return SELECT_PRODUCT


async def select_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    _, product_code, model_index_str = query.data.split(":")
    product = config.PRODUCTS.get(product_code)
    if product is None:
        await query.edit_message_text("محصول یافت نشد.")
        return ConversationHandler.END

    try:
        model_index = int(model_index_str)
        model_name = product.models[model_index]
    except (ValueError, IndexError):
        await query.edit_message_text("مدل نامعتبر است. لطفا دوباره تلاش کنید.")
        return SELECT_MODEL

    context.user_data[UD_MODEL] = model_name
    await query.edit_message_text(
        f"مدل انتخابی: {model_name}\n\n"
        f"لطفا تعداد مورد نظر خود را وارد کنید (فقط عدد):"
    )
    return ASK_QUANTITY


async def ask_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()

    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "❗️ لطفا یک عدد صحیح و مثبت برای تعداد وارد کنید."
        )
        return ASK_QUANTITY

    quantity = int(text)
    context.user_data[UD_QUANTITY] = quantity

    product_code = context.user_data[UD_PRODUCT_CODE]
    product = config.PRODUCTS[product_code]
    total = quantity * product.price

    summary = (
        "🧾 خلاصه سفارش:\n\n"
        f"🛍 محصول: {product.name}\n"
        f"🎨 مدل: {context.user_data[UD_MODEL]}\n"
        f"🔢 تعداد: {quantity}\n"
        f"💰 قیمت واحد: {product.price:,} تومان\n"
        f"💵 مبلغ کل: {total:,} تومان\n\n"
        "آیا سفارش خود را تایید می کنید؟"
    )
    await update.message.reply_text(
        summary, reply_markup=keyboards.confirm_order_keyboard()
    )
    return CONFIRM_ORDER


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    payment_text = (
        "💳 لطفا مبلغ سفارش را به شماره کارت زیر واریز کنید:\n\n"
        f"شماره کارت: {config.CARD_NUMBER}\n"
        f"به نام: {config.CARD_OWNER}\n\n"
        "پس از واریز، لطفا تصویر رسید پرداخت را ارسال کنید 📸"
    )
    await query.edit_message_text(payment_text)
    return WAIT_RECEIPT


async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text(
            "❗️ لطفا تصویر رسید پرداخت را به صورت عکس ارسال کنید."
        )
        return WAIT_RECEIPT

    # Take the highest resolution version of the uploaded photo.
    file_id = update.message.photo[-1].file_id
    context.user_data[UD_RECEIPT_FILE_ID] = file_id

    await update.message.reply_text(
        "✅ رسید دریافت شد.\n\nلطفا نام و نام خانوادگی کامل خود را وارد کنید:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_NAME


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = (update.message.text or "").strip()
    if len(full_name) < 3:
        await update.message.reply_text(
            "❗️ لطفا نام و نام خانوادگی معتبر وارد کنید."
        )
        return ASK_NAME

    context.user_data[UD_FULL_NAME] = full_name
    await update.message.reply_text(
        "لطفا شماره تلفن خود را با استفاده از دکمه زیر ارسال کنید،\n"
        "یا آن را به صورت متنی تایپ کنید:",
        reply_markup=keyboards.phone_request_keyboard(),
    )
    return ASK_PHONE


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone: Optional[str] = None

    if update.message.contact is not None:
        phone = update.message.contact.phone_number
    elif update.message.text:
        candidate = update.message.text.strip()
        digits = candidate.replace("+", "").replace(" ", "")
        if digits.isdigit() and 8 <= len(digits) <= 15:
            phone = candidate

    if not phone:
        await update.message.reply_text(
            "❗️ شماره تلفن نامعتبر است. لطفا دوباره ارسال کنید."
        )
        return ASK_PHONE

    context.user_data[UD_PHONE] = phone
    await update.message.reply_text(
        "لطفا آدرس کامل خود را وارد کنید:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_ADDRESS


async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address = (update.message.text or "").strip()
    if len(address) < 10:
        await update.message.reply_text(
            "❗️ لطفا آدرس کامل و معتبر وارد کنید."
        )
        return ASK_ADDRESS

    context.user_data[UD_ADDRESS] = address
    await update.message.reply_text("لطفا کد پستی خود را وارد کنید:")
    return ASK_POSTAL


async def ask_postal_code(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    postal_code = (update.message.text or "").strip()
    if not postal_code.isdigit() or len(postal_code) != 10:
        await update.message.reply_text(
            "❗️ کد پستی باید ۱۰ رقم و فقط عدد باشد. لطفا دوباره وارد کنید."
        )
        return ASK_POSTAL

    user = update.effective_user
    product_code = context.user_data[UD_PRODUCT_CODE]
    product = config.PRODUCTS[product_code]

    # Persist the user's latest profile info for convenience next time.
    db.upsert_user(
        user_id=user.id,
        username=user.username,
        full_name=context.user_data[UD_FULL_NAME],
        phone=context.user_data[UD_PHONE],
        address=context.user_data[UD_ADDRESS],
        postal_code=postal_code,
    )

    order = db.create_order(
        user_id=user.id,
        username=user.username,
        product_code=product.code,
        product_name=product.name,
        model=context.user_data[UD_MODEL],
        quantity=context.user_data[UD_QUANTITY],
        price_per_item=product.price,
        full_name=context.user_data[UD_FULL_NAME],
        phone=context.user_data[UD_PHONE],
        address=context.user_data[UD_ADDRESS],
        postal_code=postal_code,
        receipt_file_id=context.user_data[UD_RECEIPT_FILE_ID],
    )

    await update.message.reply_text(
        "🎉 سفارش شما با موفقیت ثبت شد!\n\n"
        + keyboards.format_order_summary(order)
        + "\nپس از تایید پرداخت توسط ادمین، سفارش شما پردازش خواهد شد.",
        reply_markup=keyboards.main_menu_keyboard(),
    )

    await _notify_admins(context, order)

    _clear_purchase_state(context)
    return ConversationHandler.END


async def _notify_admins(context: ContextTypes.DEFAULT_TYPE, order) -> None:
    """Send the new order (with receipt photo and status buttons) to admins."""
    caption = keyboards.format_order_for_admin(order)
    for admin_id in config.ADMIN_IDS:
        try:
            if order.receipt_file_id:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=order.receipt_file_id,
                    caption=caption,
                    reply_markup=keyboards.admin_status_keyboard(order.order_number),
                )
            else:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=caption,
                    reply_markup=keyboards.admin_status_keyboard(order.order_number),
                )
        except Exception:  # noqa: BLE001 - never let one failed admin break flow
            logger.exception("Failed to notify admin %s about new order", admin_id)


# ---------------------------------------------------------------------------
# Cancel / fallback
# ---------------------------------------------------------------------------


async def cancel_purchase(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    _clear_purchase_state(context)
    await update.message.reply_text(
        "❌ فرآیند خرید لغو شد.",
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "متوجه پیام شما نشدم. لطفا از دکمه های منو استفاده کنید.",
            reply_markup=keyboards.main_menu_keyboard(),
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)


# ---------------------------------------------------------------------------
# ConversationHandler factory
# ---------------------------------------------------------------------------


def build_purchase_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("خرید محصول جدید"), start_purchase
             )
        ],
        states={
            SELECT_PRODUCT: [
                CallbackQueryHandler(select_product, pattern=r"^product:"),
            ],
            SELECT_MODEL: [
                CallbackQueryHandler(select_model, pattern=r"^model:"),
                CallbackQueryHandler(back_to_products, pattern=r"^back_to_products$"),
            ],
            ASK_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_quantity),
            ],
            CONFIRM_ORDER: [
                CallbackQueryHandler(confirm_order, pattern=r"^confirm_order$"),
                CallbackQueryHandler(back_to_products, pattern=r"^back_to_products$"),
            ],
            WAIT_RECEIPT: [
                MessageHandler(filters.PHOTO, receive_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_receipt),
            ],
            ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name),
            ],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, ask_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone),
            ],
            ASK_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_address),
            ],
            ASK_POSTAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_postal_code),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_purchase),
            MessageHandler(filters.Regex(f"^{config.BTN_CANCEL}$"), cancel_purchase),
        ],
        name="purchase_conversation",
        persistent=False,
    )
