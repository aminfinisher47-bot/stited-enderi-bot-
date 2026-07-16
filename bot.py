"""
bot.py
======
Application entry point. Builds the ``telegram.ext.Application``,
registers every handler and starts polling.

Run with:

    python bot.py

Make sure to set the ``BOT_TOKEN`` environment variable (or edit
``config.py`` directly) before starting the bot.
"""

from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

import admin
import config
import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def build_application() -> Application:
    if not config.BOT_TOKEN or config.BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError(
            "BOT_TOKEN is not configured. Set the BOT_TOKEN environment "
            "variable or edit config.py before running the bot."
        )

    application = Application.builder().token(config.BOT_TOKEN).build()

    # --- core commands ------------------------------------------------
    application.add_handler(CommandHandler("start", handlers.start))

    # --- purchase flow (must be added before the generic menu handlers
    #     below so its entry point regex is matched first) -------------
    application.add_handler(handlers.build_purchase_conversation_handler())

    # --- admin order-management flow -----------------------------------
    application.add_handler(admin.build_admin_conversation_handler())

    # --- static main-menu buttons --------------------------------------
    application.add_handler(
        MessageHandler(
            filters.Regex(f"^{config.BTN_MY_ORDERS}$"), handlers.show_my_orders
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Regex(f"^{config.BTN_SUPPORT}$"), handlers.show_support
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Regex(f"^{config.BTN_CHANNELS}$"), handlers.show_channels
        )
    )

    # --- fallback for anything else -------------------------------------
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.unknown_message)
    )

    # --- error handler ----------------------------------------------------
    application.add_error_handler(handlers.error_handler)

    return application


def main() -> None:
    application = build_application()
    logger.info("Bot started. Polling for updates...")
    application.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
