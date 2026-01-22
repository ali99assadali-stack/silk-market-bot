import json
import time
import os
import threading
from datetime import datetime
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext
)

# ================== الإعدادات ==================
TOKEN = "PUT_YOUR_TOKEN_HERE"
ADMIN_ID = 7644436020
CHANNEL = "@Silk7Road"
BOT_USERNAME = "silk_7_road_bot"

OFFERS_FILE = "offers.json"
USERS_FILE = "users.json"

REF_REWARD_PER = 50
REF_REWARD_AMOUNT = 1
REF_COMMISSION_PERCENT = 5

# ================== الشروط ==================
TERMS_TEXT = (
    "🕶️ *طريق الحرير*\n\n"
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
def is_subscribed(bot, user_id):
    try:
        m = bot.get_chat_member(CHANNEL, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# ================== /start ==================
def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    args = context.args

    users.setdefault(str(uid), {
        "accepted": False,
        "referrer": None,
        "referrals": 0,
        "ref_balance": 0,
        "commission_balance": 0
    })

    if args:
        if args[0].startswith("ref_"):
            ref_id = args[0].replace("ref_", "")
            if ref_id != str(uid) and users[str(uid)]["referrer"] is None:
                if ref_id in users:
                    users[str(uid)]["referrer"] = ref_id
                    users[ref_id]["referrals"] += 1
                    if users[ref_id]["referrals"] % REF_REWARD_PER == 0:
                        users[ref_id]["ref_balance"] += REF_REWARD_AMOUNT
                    save_json(USERS_FILE, users)

        if args[0].startswith("deal_"):
            start_deal(update, context)
            return

    if not is_subscribed(context.bot, uid):
        kb = [
            [InlineKeyboardButton("📢 الاشتراك بالقناة", url=f"https://t.me/{CHANNEL.replace('@','')}")],
            [InlineKeyboardButton("🔔 تحقق", callback_data="check_sub")]
        ]
        update.message.reply_text("🔒 اشترك بالقناة أولاً", reply_markup=InlineKeyboardMarkup(kb))
        return

    if not users[str(uid)]["accepted"]:
        kb = [[InlineKeyboardButton("✅ أوافق", callback_data="accept_terms")]]
        update.message.reply_text(TERMS_TEXT, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    main_menu(update)

# ================== القائمة ==================
def main_menu(update: Update):
    msg = update.message or update.callback_query.message
    kb = [
        [InlineKeyboardButton("🛒 السوق", url=f"https://t.me/{CHANNEL.replace('@','')}")],
        [InlineKeyboardButton("➕ نشر عرض", callback_data="post_offer")],
        [InlineKeyboardButton("👥 الإحالات", callback_data="referrals")],
        [InlineKeyboardButton("📞 الدعم", callback_data="support")]
    ]
    msg.reply_text("🕶️ *طريق الحرير*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================== الأزرار ==================
def buttons(update: Update, context: CallbackContext):
    q = update.callback_query
    uid = q.from_user.id
    q.answer()

    if q.data == "check_sub":
        if is_subscribed(context.bot, uid):
            q.message.edit_text("✔️ تم التحقق")
            main_menu(update)
        else:
            q.message.reply_text("❌ اشترك بالقناة")

    elif q.data == "accept_terms":
        users[str(uid)]["accepted"] = True
        save_json(USERS_FILE, users)
        q.message.edit_text("✔️ أهلاً بك")
        main_menu(update)

    elif q.data == "support":
        q.message.reply_text("https://t.me/Silk_RoadTeam")

    elif q.data == "post_offer":
        STATES[uid] = {"step": "details"}
        q.message.reply_text("✏️ أرسل تفاصيل العرض")

    elif q.data == "referrals":
        u = users[str(uid)]
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        text = (
            f"👥 الإحالات: {u['referrals']}\n"
            f"💵 الرصيد: {u['ref_balance']}$\n"
            f"📈 العمولة: {u['commission_balance']}$\n\n"
            f"🔗 رابطك:\n{link}"
        )
        q.message.edit_text(text, disable_web_page_preview=True)

# ================== النصوص ==================
def texts(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if uid not in STATES:
        return

    state = STATES[uid]

    if state["step"] == "details":
        state["details"] = update.message.text
        state["step"] = "price"
        update.message.reply_text("💵 أرسل السعر")

    elif state["step"] == "price":
        state["price"] = update.message.text
        state["step"] = "photo"
        update.message.reply_text("🖼️ أرسل صورة")

# ================== الصور ==================
def photos(update: Update, context: CallbackContext):
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
        "created": datetime.now().isoformat()
    }
    save_json(OFFERS_FILE, offers)

    kb = [[InlineKeyboardButton("🔐 دخول الصفقة", url=f"https://t.me/{BOT_USERNAME}?start=deal_{oid}")]]
    context.bot.send_photo(CHANNEL, photo=photo_id,
                           caption=f"{state['details']}\n💵 {state['price']}",
                           reply_markup=InlineKeyboardMarkup(kb))

    update.message.reply_text("✔️ تم نشر العرض")
    STATES.pop(uid)

# ================== الصفقة ==================
def start_deal(update: Update, context: CallbackContext):
    code = context.args[0].replace("deal_", "")
    if code not in offers:
        update.message.reply_text("❌ العرض غير موجود")
        return

    o = offers[code]
    kb = [[
        InlineKeyboardButton("✅ موافق", callback_data=f"confirm_{code}"),
        InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
    ]]
    update.message.reply_text(f"{o['details']}\n💵 {o['price']}",
                              reply_markup=InlineKeyboardMarkup(kb))

def deal_buttons(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()

    if q.data == "cancel":
        q.message.edit_text("❌ ألغيت")

    elif q.data.startswith("confirm_"):
        oid = q.data.replace("confirm_", "")
        o = offers.get(oid)
        if not o:
            q.message.edit_text("❌ غير موجود")
            return

        context.bot.send_message(
            ADMIN_ID,
            f"🧾 طلب شراء\n{o['details']}\n💵 {o['price']}"
        )
        q.message.edit_text("✔️ تم إرسال الطلب")

# ================== KEEP ALIVE ==================
def keep_alive():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "Bot is running"

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ================== التشغيل ==================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(deal_buttons, pattern="^(confirm_|cancel)"))
    dp.add_handler(CallbackQueryHandler(buttons))
    dp.add_handler(MessageHandler(Filters.photo, photos))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, texts))

    threading.Thread(target=keep_alive).start()
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
