import logging
import httpx
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)

# ----------- تنظیمات اولیه -------------
BOT_TOKEN = "7570067863:AAGkAdnrGfsm9sJktt7pmCpJoxa5prJEMX0"
CHANNEL_USERNAME = "@deepseek_ai_ya"
API_KEY = "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"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-4-maverick:free"

# ----------- لاگ‌گیری -------------
logging.basicConfig(level=logging.INFO)

# ----------- مراحل گفتگو -------------
CHOOSING, CHATTING = range(2)

# بررسی عضویت کاربر
async def is_user_subscribed(user_id):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                params={"chat_id": CHANNEL_USERNAME, "user_id": user_id},
                timeout=10
            )
            result = response.json()
            status = result.get("result", {}).get("status")
            return status in ["member", "creator", "administrator"]
        except Exception as e:
            logging.error(f"خطا در بررسی عضویت: {e}")
            return False

# شروع ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subscribed = await is_user_subscribed(user.id)

    if not subscribed:
        join_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]
        ])
        await update.message.reply_text(
            "برای استفاده از ربات لطفاً ابتدا در کانال عضو شوید و سپس /start را بزنید.",
            reply_markup=join_button
        )
        return ConversationHandler.END

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله", callback_data="yes"),
         InlineKeyboardButton("❌ خیر", callback_data="no")]
    ])
    await update.message.reply_text("آیا می‌خوای چت با هوش مصنوعی شروع بشه؟", reply_markup=reply_markup)
    return CHOOSING

# واکنش به انتخاب بله یا خیر
async def choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "no":
        await query.edit_message_text("پس خداحافظ 👋")
        return ConversationHandler.END
    else:
        await query.edit_message_text("سلام. چه کمکی می تونم بهت بکنم؟")
        return CHATTING

# ارسال پیام به دیپ‌سیک (اضافه شدن دکمه لغو)
async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    await update.message.chat.send_action(action="typing")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": user_message}]
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(API_URL, headers=headers, json=data)

        result = response.json()

        # اضافه کردن دکمه لغو
        cancel_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⛔ توقف چت", callback_data="cancel_chat")]
        ])

        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
            await update.message.reply_text(reply.strip(), reply_markup=cancel_markup)
        else:
            logging.error(f"پاسخ ناقص از API: {result}")
            await update.message.reply_text("⚠️ مشکلی در دریافت پاسخ از هوش مصنوعی پیش اومد.")

    except httpx.RequestError as e:
        logging.error(f"⛔ خطا در اتصال به API: {e}")
        await update.message.reply_text("❌ ارتباط با سرور برقرار نشد. لطفاً بعداً تلاش کن.")
    except Exception as e:
        logging.exception("⚠️ خطای ناشناخته:")
        await update.message.reply_text("😓 یه خطای غیرمنتظره رخ داد. لطفاً دوباره تلاش کن.")

    return CHATTING

# هندلر جدید برای دکمه لغو
async def cancel_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("چت متوقف شد. برای شروع مجدد /start رو بزن.")
    return ConversationHandler.END

# کنسل کردن گفتگو
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("چت متوقف شد. برای شروع مجدد /start رو بزن.")
    return ConversationHandler.END

# ------------------ اجرای برنامه ------------------
if __name__ == "__main__":
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(20)
        .write_timeout(20)
        .connect_timeout(10)
        .pool_timeout(10)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(choice_handler)],
            CHATTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_ai),
                CallbackQueryHandler(cancel_chat, pattern="^cancel_chat$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True  # فعال کردن قابلیت شروع مجدد
    )

    application.add_handler(conv_handler)

    print("🤖 ربات آماده‌ست! در حال اجرا...")
    application.run_polling()
