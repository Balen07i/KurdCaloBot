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
    "من یارمەتیدەری تۆم بۆ ژماردنی کالۆری — تەنها وێنەیەکی خواردنەکەت بنێرە، "
    "ئەگەر چەند خواردنێک پێکەوە بن یەکە‌یەک هەڵیان دەبژێرم، پاشان کالۆری و "
    "پرۆتین و کاربۆهایدرەیت و چەوری‌یان بۆ دەخەمە ڕوو — بە کوردی، بێ "
    "بەرامبەر، بۆ هەمیشە.\n\n"
    "فەرمانەکان:\n"
    "📸 تەنها وێنە بنێرە بۆ شیکردنەوە\n"
    "/today - کۆی ئەمڕۆ\n"
    "/week - کۆی ئەم هەفتەیە\n\n"
    "⚠️ هەموو ژمارەکان هەڵسەنگاندنن، نەک وردی تەواو."
)

DISCLAIMER = (
    "⚠️ ئەم ئەنجامانە خەمڵاندنن و لەوانەیە بەپێی قەبارەی خواردن و "
    "شێوازی ئامادەکردن کەمێک جیاواز بن."
)

SEPARATOR = "――――――――――――"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    totals = get_today_total(user_id)
    count = get_meal_count_today(user_id)
    await update.message.reply_text(
        f"📊 کۆی ئەمڕۆ\n"
        f"🔥 {totals['kcal']} کالۆری\n"
        f"💪 {totals['protein_g']} g پرۆتین\n"
        f"🍚 {totals['carbs_g']} g کاربۆهایدرەیت\n"
        f"🥑 {totals['fat_g']} g چەوری\n\n"
        f"🍽️ {count} خواردن تۆمارکراوە"
    )


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    totals = get_week_total(user_id)
    avg_kcal = totals["kcal"] // 7
    await update.message.reply_text(
        f"📊 کۆی ئەم هەفتەیە\n"
        f"🔥 {totals['kcal']} کالۆری (تێکڕای ڕۆژانە: {avg_kcal})\n"
        f"💪 {totals['protein_g']} g پرۆتین\n"
        f"🍚 {totals['carbs_g']} g کاربۆهایدرەیت\n"
        f"🥑 {totals['fat_g']} g چەوری"
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


def _format_food_block(food: dict) -> str:
    return (
        f"{food['emoji']} {food['name_kurdish']} — {food['portion_kurdish']}\n\n"
        f"🔥 کالۆری: {food['kcal']}\n"
        f"💪 پرۆتین: {food['protein_g']} g\n"
        f"🍚 کاربۆهایدرەیت: {food['carbs_g']} g\n"
        f"🥑 چەوری: {food['fat_g']} g"
    )


def format_result(result: dict) -> str:
    foods = result["foods"]

    food_blocks = "\n\n".join(_format_food_block(f) for f in foods)

    # Only show a totals section when there's actually more than one item -
    # otherwise it would just repeat the single food block above it.
    totals_block = ""
    if len(foods) > 1:
        totals_block = (
            f"\n\n{SEPARATOR}\n"
            f"📊 کۆی گشتی:\n"
            f"🔥 کالۆری: {result['total_kcal']}\n"
            f"💪 پرۆتین: {result['total_protein_g']} g\n"
            f"🍚 کاربۆهایدرەیت: {result['total_carbs_g']} g\n"
            f"🥑 چەوری: {result['total_fat_g']} g"
        )

    return (
        f"{food_blocks}"
        f"{totals_block}\n\n"
        f"🎯 ئاستی دڵنیابوونم لە ئەنجامەکە: {result['confidence']}\n\n"
        f"💬 کورتە تێبینی:\n{result['note_kurdish']}\n\n"
        f"{result['insight_kurdish']}\n\n"
        f"{DISCLAIMER}"
    )


NO_FOOD_MESSAGE = (
    "🤔 نەمتوانی هیچ خواردنێکی ڕوونم لەم وێنەیەدا بدۆزمەوە.\n\n"
    "ئەگەر وا دەزانیت خواردن تێیدایە، تکایە وێنەیەکی ڕوونتر بنێرەوە."
)

PHOTO_TIPS_MESSAGE = (
    "❌ ببورە، نەمتوانی وێنەکە بە باشی شیکار بکەم.\n\n"
    "تکایە ئەمانە تاقی بکەرەوە:\n"
    "💡 لە شوێنێکی ڕووناکتر وێنە بگرە\n"
    "🍽️ با هەموو پلێتەکە لەناو وێنەکەدا دیار بێت\n"
    "📷 دەست لەرزۆکی کەمتر بێت (وێنەکە تیژ نەبێت)\n"
    "🔍 زۆر نزیک زووم مەکە\n\n"
    "پاشان دووبارە هەوڵبدەرەوە. 🙏"
)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    processing_msg = await update.message.reply_text("🔍 خواردنەکە شیکار دەکەم...")

    try:
        photo = update.message.photo[-1]  # highest resolution
        photo_file = await photo.get_file()
        image_bytes = bytes(await photo_file.download_as_bytearray())

        result = estimate_calories(image_bytes, media_type="image/jpeg")

        if result["status"] == "ok":
            meal_id = log_meal(user_id, result)
            await processing_msg.edit_text(
                format_result(result),
                reply_markup=build_feedback_keyboard(meal_id),
            )
        elif result["status"] == "no_food":
            await processing_msg.edit_text(NO_FOOD_MESSAGE)
        else:  # "failed" - technical failure, not a food-related answer
            await processing_msg.edit_text(PHOTO_TIPS_MESSAGE)

    except Exception:
        logger.exception("Error processing photo")
        await processing_msg.edit_text(PHOTO_TIPS_MESSAGE)


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
        else "📝 سوپاس بۆ ئاگادارکردنەوە! یارمەتیمان دەدات باشتری بکەین."
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
