# Telegram Bot - Updated for Latest Pydroid 3 (PTB 20+)
# Followers / Likes / Views / Comments Ordering Bot

import sqlite3
import logging
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# ---------------- CONFIG ----------------
TOKEN = "ENTRE YOUR BOT TOKEN"
ADMIN_ID = 7282835498  # Your Telegram User ID
MAIN_CHANNEL = "@wlzbii"  # Force-sub channel
LOGS_CHAT_ID = -1002922229766  # Logs channel
UPI_ID = "ENTRE YOUR UPI ID / PAYMENT ID"

# ---------------- PRICES ----------------
PRICES = {
    "followers": {"min": 100, "base": 20, "per": 100},   # 100 = 20 INR
    "likes": {"min": 100, "base": 11, "per": 100},       # 100 = 11 INR
    "views": {"min": 1000, "base": 10, "per": 1000},     # 1000 = 10 INR
    "comments": {"min": 20, "base": 3, "per": 20},       # 20 = 3 INR
}

# ---------------- STATES ----------------
CHOOSE_SERVICE, ENTER_QTY, WAIT_PAYMENT, WAIT_PROFILE = range(4)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("orders.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    service TEXT,
    quantity INTEGER,
    price REAL,
    payment_screenshot TEXT,
    profile_link TEXT,
    status TEXT
)
""")
conn.commit()

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Force-sub check
    member = await context.bot.get_chat_member(MAIN_CHANNEL, user.id)
    if member.status in ["left", "kicked"]:
        keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{MAIN_CHANNEL[1:]}")]]
        await update.message.reply_text(
            "🚨 You must join our channel to use this bot!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    # Main menu
    keyboard = [
        ["👤 Followers", "❤️ Likes"],
        ["👁️ Views", "💬 Comments"]
    ]
    await update.message.reply_text(
        "Welcome! Bro 🗿                                    🤖This is a Smm Panel bot\n                        by\n                   @Wlzbi\n📺Thanks For Joining My Channel!\n♻️Now Enjoy Your Service:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSE_SERVICE

# ---------------- SERVICE ----------------
async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "follower" in text: context.user_data["service"] = "followers"
    elif "like" in text: context.user_data["service"] = "likes"
    elif "view" in text: context.user_data["service"] = "views"
    elif "comment" in text: context.user_data["service"] = "comments"
    else:
        await update.message.reply_text("❌ Invalid choice. Try again.")
        return CHOOSE_SERVICE

    await update.message.reply_text("Enter the quantity you want:")
    return ENTER_QTY

# ---------------- QUANTITY ----------------
async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text)
    except:
        await update.message.reply_text("❌ Enter a valid number.")
        return ENTER_QTY

    service = context.user_data["service"]
    price_info = PRICES[service]

    if qty < price_info["min"]:
        await update.message.reply_text(f"❌ Minimum for {service} is {price_info['min']}.")
        return ENTER_QTY

    price = (qty / price_info["per"]) * price_info["base"]
    context.user_data["quantity"] = qty
    context.user_data["price"] = price

    await update.message.reply_text(
        f"✅ Order Summary:\n\nService: {service}\nQuantity: {qty}\nPrice: ₹{price}\n\n"
        f"Please pay to this UPI: {UPI_ID}\n\nSend your payment screenshot here."
    )
    return WAIT_PAYMENT

# ---------------- PAYMENT ----------------
async def payment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Please send a screenshot (image).")
        return WAIT_PAYMENT

    file_id = update.message.photo[-1].file_id
    context.user_data["payment_screenshot"] = file_id

    await update.message.reply_text("✅ Payment received!\nNow send the profile link.")
    return WAIT_PROFILE

# ---------------- PROFILE ----------------
async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile_link = update.message.text
    user = update.effective_user
    service = context.user_data["service"]
    qty = context.user_data["quantity"]
    price = context.user_data["price"]
    screenshot = context.user_data["payment_screenshot"]

    # Save to DB
    cur.execute("""
        INSERT INTO orders (user_id, username, service, quantity, price, payment_screenshot, profile_link, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user.id, user.username, service, qty, price, screenshot, profile_link, "pending"))
    conn.commit()
    order_id = cur.lastrowid

    # Send to admin
    keyboard = [[
        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{order_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}")
    ]]
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=screenshot,
        caption=f"📢 New Order #{order_id}\n\nUser: @{user.username}\nService: {service}\nQty: {qty}\nPrice: ₹{price}\nProfile: {profile_link}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Send to logs channel
    await context.bot.send_message(
        chat_id=LOGS_CHAT_ID,
        text=f"📝 Order #{order_id}\n⌨️User: @{user.username}\n🔐Service: {service}\nQty: {qty}\n🔗Profile: {profile_link}\n 💲Price: {price}"
    )

    await update.message.reply_text("✅ Order placed! Wait for admin confirmation.")
    return ConversationHandler.END

# ---------------- ADMIN BUTTONS ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.edit_message_reply_markup(reply_markup=None)  # remove buttons

    order_id = int(data.split("_")[1])
    if data.startswith("confirm"):
        cur.execute("UPDATE orders SET status=? WHERE id=?", ("confirmed", order_id))
        conn.commit()
        await query.message.reply_text("✅ Order confirmed!")
    elif data.startswith("reject"):
        cur.execute("UPDATE orders SET status=? WHERE id=?", ("rejected", order_id))
        conn.commit()
        await query.message.reply_text("❌ Order rejected!")

# ---------------- BROADCAST ----------------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = update.message.text.replace("/broadcast", "").strip()
    if not msg:
        await update.message.reply_text("Usage: /broadcast your_message")
        return

    cur.execute("SELECT DISTINCT user_id FROM orders")
    users = cur.fetchall()
    for (uid,) in users:
        try:
            await context.bot.send_message(uid, f"📢 Broadcast:\n\n{msg}")
        except:
            pass
    await update.message.reply_text("✅ Broadcast sent.")

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_service)],
            ENTER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_quantity)],
            WAIT_PAYMENT: [MessageHandler(filters.PHOTO, payment_received)],
            WAIT_PROFILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("broadcast", broadcast))

    print("🤖 Bot is running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
