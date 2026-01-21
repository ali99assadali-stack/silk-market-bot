
import json
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ================== الإعدادات ==================
TOKEN = "7566025573:AAGBL2Z832qZcrBzR1OJSX89EorkrXsQ4eo"
ADMIN_ID = 7644436020
CHANNEL = "@Silk7Road"
BOT_USERNAME = "silk_7_road_bot"

OFFERS_FILE = "offers.json"
USERS_FILE = "users.json"

# ================== نص الشروط ==================
TERMS_TEXT = (
    "🕶️ **طريق الحرير**\n\n"
    "سوق مجهول الهوية.\n"
    "لا أسماء، لا أسئلة.\n\n"
    "كل صفقة مسؤولية أصحابها.\n"
    "الدخول يعني القبول الكامل."
)

# ================== التخزين ==================
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

offers = load_json(OFFERS_FILE, {})
users = load_json(USERS_FILE, {})
STATES = {}

# ================== تحقق الاشتراك ==================
async def is_subscribed(uid, bot):
    try:
        m = await bot.get_chat_member(CHANNEL, uid)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if context.args and context.args[0].startswith("deal_"):
        await start_deal(update, context)
        return

    if not await is_subscribed(uid, context.bot):
        kb = [
            [InlineKeyboardButton("📢 الاشتراك بالقناة", url=f"https://t.me/{CHANNEL.replace('@','')}")],
            [InlineKeyboardButton("🔔 تحقق من الاشتراك", callback_data="check_sub")]
        ]
        await update.message.reply_text("🔒 لازم تشترك بالقناة أولاً", reply_markup=InlineKeyboardMarkup(kb))
        return

    if not users.get(str(uid), {}).get("accepted"):
        kb = [[InlineKeyboardButton("✅ أوافق وأدخل السوق", callback_data="accept_terms")]]
        await update.message.reply_text(TERMS_TEXT, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    await main_menu(update)

# ================== القائمة ==================
async def main_menu(update: Update):
    msg = update.message or update.callback_query.message
    kb = [
        [InlineKeyboardButton("🛒 السوق", url=f"https://t.me/{CHANNEL.replace('@','')}")],
        [InlineKeyboardButton("➕ نشر عرض", callback_data="post_offer")],
        [InlineKeyboardButton("📞 الإدارة", callback_data="support")]
    ]
    await msg.reply_text("🕶️ **طريق الحرير**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================== الأزرار ==================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    if q.data == "check_sub":
        if await is_subscribed(uid, context.bot):
            await q.message.edit_text("✔️ تم التحقق")
            await main_menu(update)
        else:
            await q.message.reply_text("❌ اشترك بالقناة ثم أعد المحاولة")

    elif q.data == "accept_terms":
        users.setdefault(str(uid), {})["accepted"] = True
        save_json(USERS_FILE, users)
        await q.message.edit_text("✔️ أهلاً بك في السوق")
        await main_menu(update)

    elif q.data == "support":
        await q.message.reply_text("📞 تواصل مع الإدارة")

    elif q.data == "post_offer":
        STATES[uid] = {"step": "details"}
        await q.message.reply_text("✏️ أرسل تفاصيل العرض")

# ================== النصوص ==================
async def texts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in STATES:
        return

    state = STATES[uid]

    if state["step"] == "details":
        state["details"] = update.message.text
        state["step"] = "price"
        await update.message.reply_text("💵 أرسل السعر")

    elif state["step"] == "price":
        state["price"] = update.message.text
        state["step"] = "photo"
        await update.message.reply_text("🖼️ أرسل صورة العرض")

# ================== الصور ==================
async def photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in STATES:
        return

    state = STATES[uid]
    if state["step"] != "photo":
        return

    photo_id = update.message.photo[-1].file_id
    oid = str(int(time.time()))

    offers[oid] = {
        "details": state["details"],
        "price": state["price"],
        "photo": photo_id,
        "seller_id": uid,
        "seller_username": update.effective_user.username,
        "created": datetime.now().isoformat()
    }
    save_json(OFFERS_FILE, offers)

    kb = [[InlineKeyboardButton("🔐 دخول الصفقة", url=f"https://t.me/{BOT_USERNAME}?start=deal_{oid}")]]
    await context.bot.send_photo(
        CHANNEL,
        photo=photo_id,
        caption=f"🕶️ عرض جديد\n\n{state['details']}\n💵 {state['price']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await update.message.reply_text("✔️ تم نشر العرض")
    STATES.pop(uid)

# ================== دخول الصفقة ==================
async def start_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = context.args[0].replace("deal_", "")
    if code not in offers:
        await update.message.reply_text("❌ العرض غير موجود")
        return

    o = offers[code]
    kb = [[
        InlineKeyboardButton("✅ موافق", callback_data=f"confirm_{code}"),
        InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
    ]]
    await update.message.reply_text(f"🔐 صفقة خاصه يتم الدفع لمحفظه الأداره ويحجز المبلغ حتى تأكيد تفاصيل التسليم لا يتم الأفصاح عن معلومات الشاري/البائع ابدا في حال تخلف البائع عن التسليم او مخالفه الشروط يتم ارجاع المبلغ كاملا اذا كنت متأكد من الشراء اضغط موافق ليتم التواصل معك.\n\n{o['details']}\n💵 {o['price']}", reply_markup=InlineKeyboardMarkup(kb))

# ================== أزرار الصفقة ==================
async def deal_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.message.edit_text("❌ ألغيت")

    elif q.data.startswith("confirm_"):
        oid = q.data.replace("confirm_", "")
        o = offers.get(oid)
        if not o:
            await q.message.edit_text("❌ الصفقة غير موجودة")
            return

        await context.bot.send_message(
            ADMIN_ID,
            f"🧾 طلب شراء\n\n"
            f"📦 {o['details']}\n"
            f"💵 {o['price']}\n\n"
            f"👤 البائع: @{o['seller_username']} | ID: {o['seller_id']}\n"
            f"👤 المشتري: @{q.from_user.username} | ID: {q.from_user.id}"
        )
        await q.message.edit_text("✔️ تم إرسال الطلب")

# ================== التشغيل ==================
def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(60)
        .read_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(deal_buttons, pattern="^(confirm_|cancel)"))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.PHOTO, photos))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texts))

    print("✅ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
