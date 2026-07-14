# bot.py
#
# Main entry point. Run with: python bot.py
# Requires env vars: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY (see .env.example)

import asyncio
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

import storage
from nutrition import (
    ACTIVITY_LABELS_KURDISH,
    GOAL_LABELS_KURDISH,
    analyze_meal,
    calculate_targets,
)
import gemini_queue
from vision import optimize_image

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ ئەم ئەنجامانە خەمڵاندنن و لەوانەیە بەپێی قەبارەی خواردن و "
    "شێوازی ئامادەکردن کەمێک جیاواز بن."
)
SEPARATOR = "――――――――――――"

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

HELP_MESSAGE = (
    "📖 فەرمانەکان:\n\n"
    "📸 وێنەی خواردن بنێرە بۆ شیکردنەوە\n"
    "/profile - دانانی زانیاری تەندروستیت (تەمەن، باڵا، کێش، ئامانج)\n"
    "/goal - گۆڕینی ئامانجت\n"
    "/today - کۆی ئەمڕۆ\n"
    "/history - دوایین خواردنەکانت\n"
    "/week - کۆی ئەم هەفتەیە\n"
    "/month - کۆی ئەم مانگە\n"
    "/reset - سڕینەوەی هەموو مێژووت\n"
    "/settings - ڕێکخستنەکان\n"
    "/help - ئەم لیستە"
)

WELCOME_MESSAGE = (
    "سڵاو! 👋\n\n"
    "من یارمەتیدەری تۆم بۆ ژماردنی کالۆری — تەنها وێنەیەکی خواردنەکەت بنێرە، "
    "ئەگەر چەند خواردنێک پێکەوە بن یەکە‌یەک هەڵیان دەبژێرم، پاشان کالۆری و "
    "پرۆتین و کاربۆهایدرەیت و چەوری‌یان بۆ دەخەمە ڕوو — بە کوردی، بێ "
    "بەرامبەر، بۆ هەمیشە.\n\n"
    "پێشنیار دەکەم /profile بەکاربهێنیت بۆ دانانی ئامانجی ڕۆژانەت، "
    "بەمجۆرە دوای هەر خواردنێک پێت دەڵێم چەند ماوە.\n\n" + HELP_MESSAGE
)


# --- Onboarding (profile setup) -------------------------------------------

ONBOARDING_QUESTIONS = {
    "age": "🎂 چەند ساڵت هەیە؟ (تەنها ژمارە بنووسە، بۆ نموونە: 25)",
    "height": "📏 باڵات چەندە؟ (بە سانتیمەتر، بۆ نموونە: 175)",
    "weight": "⚖️ کێشت چەندە؟ (بە کیلۆگرام، بۆ نموونە: 70)",
}


def _sex_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👨 نێر", callback_data="profile:sex:male"),
        InlineKeyboardButton("👩 مێ", callback_data="profile:sex:female"),
    ]])


def _goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 کەمکردنەوەی چەوری", callback_data="profile:goal:lose")],
        [InlineKeyboardButton("⚖️ پاراستنی کێش", callback_data="profile:goal:maintain")],
        [InlineKeyboardButton("💪 بەهێزکردنی ماسولکە", callback_data="profile:goal:gain")],
    ])


def _activity_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"profile:activity:{key}")]
        for key, label in ACTIVITY_LABELS_KURDISH.items()
    ]
    return InlineKeyboardMarkup(rows)


async def _start_onboarding(update: Update, user_id: int):
    storage.set_onboarding_step(user_id, "age")
    await update.message.reply_text(
        "با دەستپێبکەین! 📝\n\n" + ONBOARDING_QUESTIONS["age"]
    )


def _format_profile_summary(user: dict) -> str:
    goal_label = GOAL_LABELS_KURDISH.get(user["goal"], user["goal"])
    return (
        "✅ پرۆفایلەکەت ئامادەیە!\n\n"
        f"🎯 ئامانج: {goal_label}\n\n"
        f"📊 ئامانجی ڕۆژانەت:\n"
        f"🔥 {user['target_kcal']} کالۆری\n"
        f"💪 {user['target_protein_g']} g پرۆتین\n"
        f"🍚 {user['target_carbs_g']} g کاربۆهایدرەیت\n"
        f"🥑 {user['target_fat_g']} g چەوری\n\n"
        f"(BMR: {user['bmr']} | TDEE: {user['tdee']})"
    )


def _finish_onboarding_if_ready(user_id: int) -> dict | None:
    """If age/sex/height/weight/goal/activity are all set, computes and
    saves targets, clears onboarding state, and returns the full profile.
    Otherwise returns None."""
    user = storage.get_user(user_id)
    required = ["age", "sex", "height_cm", "weight_kg", "goal", "activity_level"]
    if not user or any(user.get(f) is None for f in required):
        return None

    targets = calculate_targets(
        sex=user["sex"], weight_kg=user["weight_kg"], height_cm=user["height_cm"],
        age=user["age"], goal=user["goal"], activity_level=user["activity_level"],
    )
    storage.update_user_fields(user_id, onboarding_step=None, **targets)
    return storage.get_user(user_id)


# --- Basic commands ---------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    if user and user.get("target_kcal"):
        await update.message.reply_text(
            _format_profile_summary(user) + "\n\nبۆ گۆڕینی زانیاریەکانت دووبارە /profile بنێرە.",
        )
        # Offer to restart, but don't force it - just start over cleanly.
        storage.update_user_fields(user_id, onboarding_step=None)
    await _start_onboarding(update, user_id)


async def goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 ئامانجی نوێت هەڵبژێرە:", reply_markup=_goal_keyboard())


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ گۆڕینی پرۆفایل", callback_data="settings:edit_profile")],
        [InlineKeyboardButton("🗑️ سڕینەوەی مێژوو", callback_data="settings:reset_ask")],
    ])
    await update.message.reply_text("⚙️ ڕێکخستنەکان:", reply_markup=keyboard)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ بەڵێ، بسڕەوە", callback_data="settings:reset_confirm"),
        InlineKeyboardButton("❌ نەخێر", callback_data="settings:reset_cancel"),
    ]])
    await update.message.reply_text(
        "🗑️ دڵنیایت لە سڕینەوەی هەموو مێژووی خواردنەکانت؟ ئەمە ناگەڕێتەوە.",
        reply_markup=keyboard,
    )


# --- Tracking commands --------------------------------------------------

def _progress_line(label_emoji: str, label: str, consumed: int, target: int | None) -> str:
    if target:
        remaining = target - consumed
        return f"{label_emoji} {label}: {consumed} / {target} ({'+' if remaining < 0 else ''}{remaining} ماوە)"
    return f"{label_emoji} {label}: {consumed}"


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    totals = storage.get_today_total(user_id)
    user = storage.get_user(user_id)

    lines = [f"📊 کۆی ئەمڕۆ ({totals['meal_count']} خواردن)\n"]
    lines.append(_progress_line("🔥", "کالۆری", totals["kcal"], user and user.get("target_kcal")))
    lines.append(_progress_line("💪", "پرۆتین", totals["protein_g"], user and user.get("target_protein_g")))
    lines.append(_progress_line("🍚", "کاربۆهایدرەیت", totals["carbs_g"], user and user.get("target_carbs_g")))
    lines.append(_progress_line("🥑", "چەوری", totals["fat_g"], user and user.get("target_fat_g")))

    if not (user and user.get("target_kcal")):
        lines.append("\nℹ️ بۆ بینینی ئامانجی ڕۆژانەت، /profile بەکاربهێنە.")

    await update.message.reply_text("\n".join(lines))


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    totals = storage.get_week_total(update.effective_user.id)
    avg = totals["kcal"] // 7
    await update.message.reply_text(
        f"📊 کۆی ئەم هەفتەیە\n"
        f"🔥 {totals['kcal']} کالۆری (تێکڕای ڕۆژانە: {avg})\n"
        f"💪 {totals['protein_g']} g پرۆتین\n"
        f"🍚 {totals['carbs_g']} g کاربۆهایدرەیت\n"
        f"🥑 {totals['fat_g']} g چەوری"
    )


async def month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    totals = storage.get_month_total(update.effective_user.id)
    avg = totals["kcal"] // 30
    await update.message.reply_text(
        f"📊 کۆی ئەم مانگە\n"
        f"🔥 {totals['kcal']} کالۆری (تێکڕای ڕۆژانە: {avg})\n"
        f"💪 {totals['protein_g']} g پرۆتین\n"
        f"🍚 {totals['carbs_g']} g کاربۆهایدرەیت\n"
        f"🥑 {totals['fat_g']} g چەوری"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Bot-wide runtime stats (not per-user) - operator-facing observability.
    Not gated by any admin check since this app has no auth concept yet;
    if you want to restrict it later, check update.effective_user.id
    against your own Telegram user ID here.
    """
    s = gemini_queue.get_stats_summary()
    circuit_line = "🔴 داخراوە (کورتکردنەوەی خێرا چالاکە)" if s["circuit_open"] else "🟢 کراوەیە"
    await update.message.reply_text(
        f"📈 ئاماری کارکردن (تیمی {s['uptime_minutes']} خولەک):\n\n"
        f"📸 کۆی داواکاریەکان: {s['total_submitted']}\n"
        f"♻️ کاش هیت: {s['cache_hits']} ({s['cache_hit_rate_pct']}%)\n"
        f"✅ سەرکەوتوو: {s['successful_analyses']}\n"
        f"🤔 هیچ خواردن نەدۆزرایەوە: {s['no_food_results']}\n"
        f"🚦 هەڵەی سنووری داواکاری: {s['rate_limited_failures']}\n"
        f"❌ هەڵەی تر: {s['other_failures']}\n"
        f"🔁 قەڵبی سنووردار کراوە: {s['circuit_breaker_trips']} جار\n\n"
        f"⏱️ ئێستا خێرایی نێوان داواکاریەکان: {s['current_pacing_interval']}s\n"
        f"⚡ کورتکردنەوەی خێرا: {circuit_line}\n"
        f"📥 قەبارەی نۆرە: {s['queue_depth']}\n"
        f"💾 بیرگە: {s['cached_entries']} خواردن، {s['tracked_users']} بەکارهێنەر"
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meals = storage.get_recent_meals(update.effective_user.id, limit=10)
    if not meals:
        await update.message.reply_text("هێشتا هیچ خواردنێکت تۆمار نەکردووە.")
        return

    lines = ["🕒 دوایین خواردنەکانت:\n"]
    for m in meals:
        time_str = m["created_at"][:16].replace("T", " ")
        lines.append(f"• {time_str} — {m['food_name_kurdish']} ({m['kcal']} کالۆری)")

    await update.message.reply_text("\n".join(lines))


# --- Meal result formatting ----------------------------------------------

def build_feedback_keyboard(meal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👍 ڕاستە", callback_data=f"fb:{meal_id}:correct"),
        InlineKeyboardButton("👎 هەڵەیە", callback_data=f"fb:{meal_id}:wrong"),
        InlineKeyboardButton("✏️ ڕاستکردنەوە", callback_data=f"fb:{meal_id}:fix"),
    ]])


def _format_food_block(food: dict) -> str:
    return (
        f"{food['emoji']} {food['name_kurdish']} — {food['portion_kurdish']}\n\n"
        f"🔥 کالۆری: {food['kcal']}\n"
        f"💪 پرۆتین: {food['protein_g']} g\n"
        f"🍚 کاربۆهایدرەیت: {food['carbs_g']} g\n"
        f"🥑 چەوری: {food['fat_g']} g"
    )


def _format_alternatives(alternatives: list[dict]) -> str:
    if not alternatives:
        return ""
    lines = ["\n\n🤔 دڵنیا نیم لە هەندێک بەشی خواردنەکە:"]
    for alt in alternatives:
        lines.append(
            f"• {alt.get('scenario_kurdish', '')} → نزیکەی {alt.get('total_kcal', 0)} کالۆری "
            f"({alt.get('explanation_kurdish', '')})"
        )
    return "\n".join(lines)


def format_result(result: dict, user: dict | None) -> str:
    foods = result["foods"]
    food_blocks = "\n\n".join(_format_food_block(f) for f in foods)

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

    total = {
        "kcal": result["total_kcal"], "protein_g": result["total_protein_g"],
        "carbs_g": result["total_carbs_g"], "fat_g": result["total_fat_g"],
    }
    goal = user.get("goal") if user else None
    quality_line = analyze_meal(total, user, goal)

    alt_block = _format_alternatives(result.get("alternatives", []))

    return (
        f"{food_blocks}"
        f"{totals_block}"
        f"{alt_block}\n\n"
        f"🎯 ئاستی دڵنیابوونم لە ئەنجامەکە: {result['confidence']}\n\n"
        f"💬 کورتە تێبینی:\n{result['note_kurdish']}\n\n"
        f"{quality_line}\n\n"
        f"{result['insight_kurdish']}\n\n"
        f"{DISCLAIMER}"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Per-user cooldown check happens BEFORE we even touch the queue, so a
    # spammy user can't burn shared Gemini quota that other users need.
    cooldown_remaining = gemini_queue.check_user_cooldown(user_id)
    if cooldown_remaining > 0:
        await update.message.reply_text(gemini_queue.COOLDOWN_MESSAGE_KURDISH)
        return
    gemini_queue.mark_user_request(user_id)

    processing_msg = await update.message.reply_text("🔍 خواردنەکە شیکار دەکەم...")

    try:
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        image_bytes = bytes(await photo_file.download_as_bytearray())

        # Optimize BEFORE enqueueing, not inside the worker - a queue full
        # of full-size phone photos is real, avoidable memory pressure
        # under any backlog. Runs in a thread so resizing doesn't block
        # the event loop for other users mid-request.
        image_bytes = await asyncio.to_thread(optimize_image, image_bytes)

        corrections = storage.get_all_corrections()
        result, queue_position = await gemini_queue.submit_photo_job(
            image_bytes, "image/jpeg", corrections
        )

        if queue_position > 0 and result.get("reason") != "queue_full":
            # Only worth mentioning if they actually had to wait behind
            # someone else - avoids noise for the common case.
            try:
                await processing_msg.edit_text(
                    f"🔍 لە نۆرەدایت ({queue_position} کەس لەپێش تۆن)، تکایە چاوەڕێ بکە..."
                )
            except Exception:
                pass  # non-critical - if this edit fails, just proceed silently

        if result["status"] == "ok":
            user = storage.get_user(user_id)
            meal_id = storage.log_meal(user_id, result)
            await processing_msg.edit_text(
                format_result(result, user),
                reply_markup=build_feedback_keyboard(meal_id),
            )
        elif result["status"] == "no_food":
            await processing_msg.edit_text(NO_FOOD_MESSAGE)
        elif result.get("reason") == "queue_full":
            await processing_msg.edit_text(gemini_queue.QUEUE_FULL_MESSAGE_KURDISH)
        elif result.get("reason") == "rate_limited":
            await processing_msg.edit_text(gemini_queue.RATE_LIMIT_MESSAGE_KURDISH)
        else:
            await processing_msg.edit_text(PHOTO_TIPS_MESSAGE)

    except Exception:
        logger.exception("[UNEXPECTED] Error in handle_photo")
        await processing_msg.edit_text(PHOTO_TIPS_MESSAGE)


# --- Callback (button) handling -------------------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    parts = (query.data or "").split(":")
    domain = parts[0]

    if domain == "fb":
        await _handle_feedback_callback(query, user_id, parts)
    elif domain == "profile":
        await _handle_profile_callback(query, user_id, parts)
    elif domain == "settings":
        await _handle_settings_callback(query, user_id, parts)


async def _handle_feedback_callback(query, user_id: int, parts: list[str]):
    _, meal_id_str, choice = parts
    meal_id = int(meal_id_str)

    if choice == "correct":
        storage.set_feedback(meal_id, "correct")
        original_text = query.message.text or ""
        await query.edit_message_text(f"{original_text}\n\n✅ سوپاس! ئەمە یارمەتیمان دەدات باشتر بین.")
    elif choice == "wrong":
        storage.set_feedback(meal_id, "wrong")
        original_text = query.message.text or ""
        await query.edit_message_text(f"{original_text}\n\n📝 سوپاس بۆ ئاگادارکردنەوە!")
    elif choice == "fix":
        storage.set_pending_correction(user_id, meal_id)
        await query.message.reply_text(
            "✏️ باشە، ناوی ڕاستی خواردنەکە بنووسە (بە کوردی)، من فێری دەبم بۆ داهاتوو."
        )


async def _handle_profile_callback(query, user_id: int, parts: list[str]):
    _, field, value = parts

    if field == "sex":
        storage.update_user_fields(user_id, sex=value)
        storage.set_onboarding_step(user_id, "height")
        await query.message.reply_text(ONBOARDING_QUESTIONS["height"])
    elif field == "goal":
        storage.update_user_fields(user_id, goal=value)
        profile = _finish_onboarding_if_ready(user_id)
        if profile:
            await query.message.reply_text(_format_profile_summary(profile))
        else:
            storage.set_onboarding_step(user_id, "activity")
            await query.message.reply_text(
                "📈 ئاستی چالاکیت چۆنە؟", reply_markup=_activity_keyboard()
            )
    elif field == "activity":
        storage.update_user_fields(user_id, activity_level=value)
        profile = _finish_onboarding_if_ready(user_id)
        if profile:
            await query.message.reply_text(_format_profile_summary(profile))
        else:
            await query.message.reply_text("🎯 ئامانجت چیە؟", reply_markup=_goal_keyboard())


async def _handle_settings_callback(query, user_id: int, parts: list[str]):
    action = parts[1]

    if action == "edit_profile":
        storage.set_onboarding_step(user_id, "age")
        await query.message.reply_text("با دەستپێبکەین! 📝\n\n" + ONBOARDING_QUESTIONS["age"])
    elif action == "reset_ask":
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ بەڵێ، بسڕەوە", callback_data="settings:reset_confirm"),
            InlineKeyboardButton("❌ نەخێر", callback_data="settings:reset_cancel"),
        ]])
        await query.message.reply_text(
            "🗑️ دڵنیایت لە سڕینەوەی هەموو مێژووی خواردنەکانت؟ ئەمە ناگەڕێتەوە.",
            reply_markup=keyboard,
        )
    elif action == "reset_confirm":
        storage.reset_user_history(user_id)
        await query.edit_message_text("✅ هەموو مێژووی خواردنەکانت سڕایەوە.")
    elif action == "reset_cancel":
        await query.edit_message_text("❌ هیچ شتێک نەسڕایەوە.")


# --- Free-text handling (onboarding answers + corrections) ----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    user = storage.get_user(user_id)

    # Priority 1: a pending correction takes precedence over onboarding.
    if user and user.get("pending_correction_meal_id"):
        meal = storage.get_meal(user["pending_correction_meal_id"])
        wrong_name = meal["food_name_kurdish"] if meal else "نەناسراو"
        storage.save_correction(user_id, wrong_name=wrong_name, correct_name_kurdish=text)
        storage.set_pending_correction(user_id, None)
        await update.message.reply_text(
            f"✅ سوپاس! لە جاری داهاتوودا، خواردنی وەک ئەمە باشتر دەناسمەوە."
        )
        return

    # Priority 2: an active onboarding step (age/height/weight are free text).
    step = user.get("onboarding_step") if user else None
    if step == "age":
        if text.isdigit() and 10 <= int(text) <= 100:
            storage.update_user_fields(user_id, age=int(text))
            storage.set_onboarding_step(user_id, "sex")
            await update.message.reply_text("🚻 ڕەگەزت چیە؟", reply_markup=_sex_keyboard())
        else:
            await update.message.reply_text("تکایە ژمارەیەکی دروست بنووسە (بۆ نموونە: 25)")
        return

    if step == "height":
        try:
            height = float(text)
            if not (100 <= height <= 250):
                raise ValueError
            storage.update_user_fields(user_id, height_cm=height)
            storage.set_onboarding_step(user_id, "weight")
            await update.message.reply_text(ONBOARDING_QUESTIONS["weight"])
        except ValueError:
            await update.message.reply_text("تکایە ژمارەیەکی دروست بنووسە بە سانتیمەتر (بۆ نموونە: 175)")
        return

    if step == "weight":
        try:
            weight = float(text)
            if not (30 <= weight <= 300):
                raise ValueError
            storage.update_user_fields(user_id, weight_kg=weight)
            storage.set_onboarding_step(user_id, "goal")
            await update.message.reply_text("🎯 ئامانجت چیە؟", reply_markup=_goal_keyboard())
        except ValueError:
            await update.message.reply_text("تکایە ژمارەیەکی دروست بنووسە بە کیلۆگرام (بۆ نموونە: 70)")
        return

    # No relevant state - gentle nudge instead of silence.
    await update.message.reply_text("📸 وێنەیەکی خواردن بنێرە، یان /help بنووسە بۆ بینینی فەرمانەکان.")


async def _post_init(application):
    # Must start the worker from inside the running event loop - this hook
    # is PTB's supported way to do that, runs once before polling begins.
    gemini_queue.start_worker()
    logger.info("[STARTUP] Gemini request queue worker is running")


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    storage.init_db()

    # concurrent_updates=True is essential here, not optional: PTB
    # processes updates one at a time by default and does NOT start
    # dispatching the next update until the current handler's coroutine
    # returns. Since a photo handler can legitimately await the Gemini
    # queue for a while (rate-limit retries), leaving this at the default
    # meant every OTHER user's update - including their own instant
    # "🔍 analyzing" message - waited behind whatever the current photo
    # was doing. This was the real cause of the "7 minute delay before
    # anything happens" bug. Enabling this makes every update dispatch
    # immediately into its own task; the actual Gemini call pacing and
    # rate-limit protection is still fully enforced by gemini_queue's
    # single sequential worker, completely independent of this setting.
    app = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("goal", goal_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
