import sqlite3
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters
)

TOKEN = "8772772021:AAFutRcxc3CKO1CYTwtU5QSFWLeTZT-Uwms"
GROUP_ID = -1003703246025
ADMINS = [8368944953]

conn = sqlite3.connect("taxi.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
first_name TEXT,
last_name TEXT,
phone TEXT,
lat REAL,
lon REAL,
price INTEGER,
status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pricing(
id INTEGER PRIMARY KEY,
base_price INTEGER,
per_km INTEGER
)
""")

cursor.execute("""
INSERT OR IGNORE INTO pricing(id, base_price, per_km)
VALUES(1,5000,1500)
""")

conn.commit()

def get_price():
    cursor.execute("SELECT base_price FROM pricing WHERE id=1")
    return cursor.fetchone()[0]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["🚕 Taksi chaqirish"],
        ["📜 Buyurtmalarim"]
    ]

    if update.effective_user.id in ADMINS:
        keyboard.append(["📊 Admin Panel"])

    await update.message.reply_text(
        "🚕 Taxi servisga xush kelibsiz!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 Ismingizni kiriting")
    return 1

async def first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["first_name"] = update.message.text
    await update.message.reply_text("👤 Familyangizni kiriting")
    return 2

async def last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["last_name"] = update.message.text

    button = KeyboardButton("📍 Lokatsiyani yuborish", request_location=True)

    await update.message.reply_text(
        "📍 Joylashuvingizni yuboring",
        reply_markup=ReplyKeyboardMarkup([[button]], resize_keyboard=True)
    )

    return 3

async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):

    loc = update.message.location

    context.user_data["lat"] = loc.latitude
    context.user_data["lon"] = loc.longitude

    button = KeyboardButton("📞 Telefon yuborish", request_contact=True)

    await update.message.reply_text(
        "📞 Telefon raqamingizni yuboring",
        reply_markup=ReplyKeyboardMarkup([[button]], resize_keyboard=True)
    )

    return 4

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):

    phone = update.message.contact.phone_number
    user = update.message.from_user

    first_name = context.user_data["first_name"]
    last_name = context.user_data["last_name"]
    lat = context.user_data["lat"]
    lon = context.user_data["lon"]

    price = get_price()

    cursor.execute("""
    INSERT INTO orders(user_id,first_name,last_name,phone,lat,lon,price,status)
    VALUES(?,?,?,?,?,?,?,?)
    """, (user.id, first_name, last_name, phone, lat, lon, price, "new"))

    conn.commit()

    order_id = cursor.lastrowid

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚕 Buyurtmani olish", callback_data=f"take_{order_id}")]
    ])

    await context.bot.send_message(
        GROUP_ID,
        f"""
🚕 YANGI BUYURTMA

👤 {first_name} {last_name}
📞 {phone}

💰 Narx: {price} so'm

📍 Lokatsiya
https://maps.google.com/?q={lat},{lon}

🆔 Buyurtma ID: {order_id}
""",
        reply_markup=keyboard
    )

    await update.message.reply_text(
        "✅ Buyurtmangiz yuborildi!\nHaydovchi tez orada bog‘lanadi."
    )

    return ConversationHandler.END

async def take_order(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[1])

    cursor.execute("SELECT status,user_id FROM orders WHERE id=?", (order_id,))
    data = cursor.fetchone()

    if data[0] != "new":
        await query.answer("❌ Bu buyurtma allaqachon olingan", show_alert=True)
        return

    cursor.execute("UPDATE orders SET status='taken' WHERE id=?", (order_id,))
    conn.commit()

    await query.edit_message_text("🚕 Buyurtma haydovchi tomonidan olindi")

    await context.bot.send_message(
        data[1],
        f"🚕 Haydovchi buyurtmangizni oldi!\nBuyurtma ID: {order_id}"
    )

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    cursor.execute(
        "SELECT id,price,status FROM orders WHERE user_id=?",
        (user_id,)
    )

    orders = cursor.fetchall()

    if not orders:
        await update.message.reply_text("📭 Sizda buyurtmalar yo'q")
        return

    text = "📜 Sizning buyurtmalaringiz\n\n"

    for o in orders:
        text += f"🆔 {o[0]} | 💰 {o[1]} so'm | 📊 {o[2]}\n"

    await update.message.reply_text(text)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in ADMINS:
        return

    keyboard = [
        ["💰 Narxni o'zgartirish"],
        ["📊 Statistika"]
    ]

    await update.message.reply_text(
        "📊 Admin panel",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def change_price(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in ADMINS:
        return

    await update.message.reply_text("Yangi narxni kiriting:")
    return 10

async def save_price(update: Update, context: ContextTypes.DEFAULT_TYPE):

    price = int(update.message.text)

    cursor.execute(
        "UPDATE pricing SET base_price=? WHERE id=1",
        (price,)
    )

    conn.commit()

    await update.message.reply_text(f"✅ Yangi narx: {price} so'm")

    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute("SELECT COUNT(*) FROM orders")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='taken'")
    taken = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(price) FROM orders")
    income = cursor.fetchone()[0]

    await update.message.reply_text(
        f"""
📊 STATISTIKA

🚕 Jami buyurtmalar: {total}
🚕 Olingan buyurtmalar: {taken}
💰 Umumiy summa: {income if income else 0} so'm
"""
    )

order_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("🚕 Taksi chaqirish"), order)],
    states={
        1: [MessageHandler(filters.TEXT & ~filters.COMMAND, first_name)],
        2: [MessageHandler(filters.TEXT & ~filters.COMMAND, last_name)],
        3: [MessageHandler(filters.LOCATION, location)],
        4: [MessageHandler(filters.CONTACT, phone)]
    },
    fallbacks=[]
)

price_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("💰 Narxni o'zgartirish"), change_price)],
    states={
        10: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_price)]
    },
    fallbacks=[]
)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(order_conv)
app.add_handler(price_conv)

app.add_handler(MessageHandler(filters.Regex("📜 Buyurtmalarim"), my_orders))
app.add_handler(MessageHandler(filters.Regex("📊 Admin Panel"), admin_panel))
app.add_handler(MessageHandler(filters.Regex("📊 Statistika"), stats))

app.add_handler(CallbackQueryHandler(take_order, pattern="take_"))

print("🚕 Taxi bot ishga tushdi...")
app.run_polling()