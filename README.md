# Telegram Shop Bot

A production-ready Telegram shop bot built with **Python 3.12** and
**python-telegram-bot v21+**. Customers can browse products, place
card-to-card orders, upload payment receipts, and track order status.
Admins manage every order through inline buttons.

## Features

- 🛒 Product catalog with active/inactive products
- 🎨 Multiple models per product
- 💳 Card-to-card payment flow with receipt upload
- 📦 "My Orders" history with live status and tracking code
- 🔔 Automatic order notifications to admins (with receipt photo)
- 🛠 Admin panel driven entirely by inline keyboards
- 🚚 Tracking-code collection when an order is marked "Sent"
- 📣 Automatic customer notification on every status change
- 💬 Support and 📢 Channels buttons
- SQLite storage, tables auto-created on first run
- Fully typed, modular, `ConversationHandler`-based, no global state

## Project structure

```
telegram_shop_bot/
├── bot.py            # Application entry point / handler registration
├── config.py         # Static configuration: products, admins, texts
├── database.py       # SQLite access layer (users & orders)
├── handlers.py       # Customer-facing handlers + purchase conversation
├── admin.py          # Admin panel: status changes & tracking codes
├── keyboards.py       # Reply/inline keyboard builders + text formatting
├── requirements.txt
└── README.md
```

## Setup

1. **Create a virtual environment (recommended)**

   ```bash
   python3.12 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your bot token**

   Set it as an environment variable:

   ```bash
   export BOT_TOKEN="123456789:AAExampleTokenFromBotFather"
   ```

   Or edit `BOT_TOKEN` directly at the top of `config.py`.

4. **Review business configuration**

   Open `config.py` to adjust:
   - `ADMIN_IDS` — Telegram numeric user ids allowed to manage orders
   - `PRODUCTS` — product catalog, prices and models
   - `CARD_NUMBER` / `CARD_OWNER` — payment card details
   - `SUPPORT_CONTACTS` / `CHANNELS` — support and channel links

5. **Run the bot**

   ```bash
   python bot.py
   ```

   The SQLite database file (`shop.db` by default) is created
   automatically in the working directory the first time the bot runs.

## How the purchase flow works

1. Customer taps **🛒 خرید محصول جدید**
2. Chooses a product (inactive products immediately reply with the
   "not available" message)
3. Chooses a model
4. Enters the desired quantity (validated as a positive integer)
5. Reviews an order summary showing the total price
6. Confirms and receives card-to-card payment instructions
7. Uploads a photo of the payment receipt
8. Provides full name, phone number (native contact button or typed),
   address and postal code
9. The order is saved with a unique order number and both admins are
   notified immediately, including the receipt photo and an inline
   status-management keyboard

## How admins manage orders

Each new order arrives as a message to both admins with 5 status
buttons: Waiting, Preparing, Sent, Delivered, Cancelled.

- Selecting **Sent** prompts the admin to type a tracking code; once
  entered, it is saved to the database and the customer is notified
  automatically along with the code.
- Selecting any other status updates the order immediately and
  notifies the customer.
- Only user ids listed in `config.ADMIN_IDS` may use these buttons.

## Notes on state management

- No global/module-level mutable state is used for per-user data.
- All in-progress purchase data lives in `context.user_data`, which
  python-telegram-bot scopes per chat automatically.
- The admin "waiting for tracking code" state is handled the same
  way, scoped to the admin's own chat.

## Extending the bot

- To add more products or models, edit the `PRODUCTS` dictionary in
  `config.py` — no other code changes are required.
- To persist data elsewhere (e.g. PostgreSQL), only `database.py`
  needs to change; the rest of the codebase depends solely on the
  `Database`/`Order` interface defined there.
