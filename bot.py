# bot.py
#
# Main entry point. Run with: python bot.py
# Requires env vars: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY (see .env.example)

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from storage import (
    get_meal_count_today,
    get_today_total,
    get_week_total,
    init_db,
    log_meal,
    set_feedback,
)
from vision import estimate_calories

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "سڵاو! 👋\n\n"
    "من بۆتی ژمارەی کالۆری و بژایی مە. تەنها وێنەیەکی خواردنەکەت بنێرە، "
    "منیش خێرا کالۆری، پرۆتین، کاربۆهایدرەیت و چەوری‌ی خواردنەکەت "
    "بە کوردی بۆت دەنێرمەوە — بێ بەرامبەر و بۆ هەمیشە.\n\n"
    "فەرمانەکان:\n"
    "📸 تەنها وێنە بنێرە بۆ شیکردنەوە\n"
    "/today - کۆی ئەمڕۆ\n"
    "/week - کۆی ئەم هەفتەیە\n\n"
    "⚠️ تێبینی: هەموو ژمارەکان هەڵسەنگاندنێکن، دەکرێت بەگوێرەی قەبارەی "
    "خواردن و شێوازی چێشتلێنان جیاواز بن — نەک وردی تەواو."
)

CONFIDENCE_LABEL = {
    "high": "🎯 دڵنیایی بەرز",
    "medium": "🎯 دڵنیایی مامناوەند",
    "low": "🎯 دڵنیایی نزم — تکایە پشتڕاستی بکەوە",
}

DISCLAIMER = (
    "⚠️ ئەمانە هەڵسەنگاندنن، دەکرێت بەگوێرەی قەبارەی خواردن و "
    "شێوازی چێشتلێنان جیاواز بن."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    totals = get_today_total(user_id)
    count = get_meal_count_today(user_id)
    await update.message.reply_text(
        f"📊 کۆی ئەمڕۆ\n"
        f"🔥 {totals['kcal']} کالۆری\n"
        f"💪 {totals['protein_g']}g پرۆتین\n"
        f"🍚 {totals['carbs_g']}g کاربۆهایدرەیت\n"
        f"🥑 {totals['fat_g']}g چەوری\n\n"
        f"🍽️ {count} خواردن تۆمارکراوە"
    )


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    totals = get_week_total(user_id)
    avg_kcal = totals["kcal"] // 7
    await update.message.reply_text(
        f"📊 کۆی ئەم هەفتەیە\n"
        f"🔥 {totals['kcal']} کالۆری (تێکڕای رۆژانە: {avg_kcal})\n"
        f"💪 {totals['protein_g']}g پرۆتین\n"
        f"🍚 {totals['carbs_g']}g کاربۆهایدرەیت\n"
        f"🥑 {totals['fat_g']}g چەوری"
    )


def build_feedback_keyboard(meal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍 ڕاستە", callback_data=f"fb:{meal_id}:correct"),
                InlineKeyboardButton("👎 هەڵەیە", callback_data=f"fb:{meal_id}:wrong"),
            ]
        ]
    )


def format_result(result: dict) -> str:
    confidence_text = CONFIDENCE_LABEL.get(
        result.get("confidence", "low"), CONFIDENCE_LABEL["low"]
    )
    matched_note = (
        " ✅ لە لیستی خواردنە کوردیەکان" if result.get("matched_glossary") else ""
    )
    return (
        f"🍲 {result.get('food_name_kurdish', 'نەناسراو')}"
        f" ({result.get('food_name_english', '')})\n"
        f"🔥 {result.get('estimated_kcal', 0)} کالۆری\n"
        f"💪 {result.get('protein_g', 0)}g پرۆتین\n"
        f"🍚 {result.get('carbs_g', 0)}g کاربۆهایدرەیت\n"
        f"🥑 {result.get('fat_g', 0)}g چەوری\n"
        f"{confidence_text}{matched_note}\n\n"
        f"{result.get('note_kurdish', '')}\n"
        f"{DISCLAIMER}"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    processing_msg = await update.message.reply_text("🔍 خواردنەکە شیکار دەکەم...")

    try:
        photo = update.message.photo[-1]  # highest resolution
        photo_file = await photo.get_file()
        image_bytes = bytes(await photo_file.download_as_bytearray())

        result = estimate_calories(image_bytes, media_type="image/jpeg")
        meal_id = log_meal(user_id, result)

        await processing_msg.edit_text(
            format_result(result),
            reply_markup=build_feedback_keyboard(meal_id),
        )

    except Exception:
        logger.exception("Error processing photo")
        await processing_msg.edit_text(
            "❌ ببورە، هەڵەیەک ڕوویدا. تکایە دووبارە هەوڵبدەرەوە."
        )


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, meal_id_str, choice = query.data.split(":")
        meal_id = int(meal_id_str)
    except (ValueError, AttributeError):
        return

    set_feedback(meal_id, "correct" if choice == "correct" else "wrong")

    thanks = (
        "✅ سوپاس! ئەمە یارمەتیمان دەدات باشتر بین."
        if choice == "correct"
        else "📝 سوپاس بۆ ئاگادارکردنەوە! ئەمە یارمەتیمان دەدات لیستەکە باشتر بکەین."
    )

    # Keep the original result text, drop the buttons, append a thank-you line
    original_text = query.message.text or ""
    await query.edit_message_text(f"{original_text}\n\n{thanks}")


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    init_db()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^fb:"))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
