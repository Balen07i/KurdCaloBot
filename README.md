# Kurdish Calorie Bot — Setup Guide (100% Free Stack)

Two free API keys, no credit card, no paid services anywhere in this project.

## What this bot does now
1. **Photo analysis**: send a meal photo, Gemini identifies every distinct food (including drinks, sauces, oils, bread, sides, garnishes), estimates portions using visible reference objects (plate/bowl/spoon/hand), and calculates calories + macros per item and as a total.
2. **Genuine uncertainty handling**: for visually confusable foods (e.g. pomegranate molasses vs tomato sauce), the bot gives its best estimate plus 1-2 alternative readings instead of silently guessing — but only when there's real ambiguity, not by default.
3. **Personalized targets**: `/profile` walks through a short setup (age, sex, height, weight, goal, activity level) via buttons/short text answers, then calculates BMR, TDEE, and daily calorie/protein/carb/fat targets (Mifflin-St Jeor equation — the standard free formula, no paid nutrition API needed).
4. **Daily tracking**: every meal is logged; `/today`, `/week`, `/month` show totals, and `/today` shows progress against your personal targets once set up.
5. **Meal quality feedback**: after each meal, a rule-based (not AI, so it's instant and free) read on whether it's high-protein, high-carb, high-fat, balanced, and whether it fits your current goal.
6. **User corrections that actually help**: tap ✏️ on any result to correct it in your own words. That correction is saved and automatically included as extra context on every future photo analysis for every user — a real free "learning" loop, no model retraining, no external service.
7. **Full command set**: `/start /help /profile /goal /today /history /week /month /reset /settings`, with inline buttons wherever they save typing.

## Review: weaknesses in the previous version (what this update addresses)
- **Glossary was too narrow** (31 dishes, no drinks/desserts/fruits/vegetables/sauces/oils) — now 64+ entries across all those categories.
- **No mechanism to distinguish visually similar foods** — added an explicit confusable-pairs list (starting with pomegranate molasses vs tomato sauce) that teaches the model what to actually look for, plus the alternatives system for genuine ambiguity.
- **No portion-estimation anchor** — the model had no instruction to use plates/hands/spoons as scale references; now it does.
- **All estimates were single-shot with no user memory** — corrections vanished after each message. Now they're persisted and reused.
- **No personalization** — same targets-free experience for every user regardless of goals. Now there's a full profile + daily targets system.
- **No qualitative meal feedback** — users got numbers with no interpretation of whether the meal fit their goals.
- **Everything free-text driven** — every interaction required typing. Now buttons handle sex/goal/activity/confirmation choices.

## Known limitations (honest, not glossed over)
- **Portion accuracy from a single 2D photo has a hard ceiling.** No free vision API can truly measure volume from one angle — reference-object anchoring helps a lot but this will never be lab-accurate. This is a property of photo-based estimation in general, not something more prompting fully solves.
- **The correction system is prompt-based, not real training.** It works well at moderate scale (tens to low hundreds of corrections fit comfortably in the prompt), but isn't a substitute for a real fine-tuned model if you eventually have thousands of corrections — the fix at that point would be pruning to the most valuable ones, not a code change.
- **Free Gemini tier rate limits still apply** (see below) — unchanged from before, just worth repeating since usage will grow with more features.

## Deployment (mostly unchanged from before)
Same two keys as before — nothing new to set up:

1. **Telegram**: @BotFather → `/newbot` → copy the token.
2. **Gemini**: https://aistudio.google.com/apikey → sign in → "Create API key". Still genuinely free, no card, no expiration.
3. Fill in `.env` (rename from `.env.example`), same two variables: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`.
4. Deploy on Railway/Render the same way as before: push this folder, set the two env vars, start command `python bot.py`.
5. **This is safe to deploy directly over your already-running bot.** The database migration (new `users` and `corrections` tables, new columns) runs automatically on startup and never touches or drops existing data — verified with a migration test against a simulated copy of the old schema before shipping this.

## New files in this version
- `nutrition.py` — BMR/TDEE/target math (Mifflin-St Jeor) and rule-based meal quality analysis. Pure calculation, no AI call, instant and free.
- Everything else is the same files as before, extended in place — no rewrite, no new dependencies (`requirements.txt` is unchanged).

## Improving the glossary and confusable pairs
Same as before — `kurdish_foods.py` is still a plain list, copy-paste to add a dish. Two things are new in this file:
- `CONFUSABLE_PAIRS` — add more pairs here as you discover them (format matches the pomegranate-molasses example already in the file).
- `find_glossary_match()` — fuzzy matching, no need to touch this unless you want to tune the similarity cutoff.

Run `python review_feedback.py` anytime to see both 👎 flagged results AND all corrections learned so far in one place.

⚠️ **Still true, still important**: I'm not a native Kurdish speaker. I've written every string (including 30+ new ones for profile setup, meal analysis, and the new commands) in what I believe is natural, everyday Sorian — but please read through `bot.py`, `vision.py`'s prompt, and `nutrition.py`'s Kurdish labels before wider launch.

## What's intentionally not built (would break the "100% free" or "keep it simple" constraints)
- Full ConversationHandler-based multi-step flows — used a simpler DB-backed step tracker instead, which is more restart-safe anyway.
- Any external nutrition database API — all values are hand-curated in `kurdish_foods.py`, which is actually more reliable for Kurdish dishes specifically than a generic (and often paid) nutrition API would be.
- Photo-based learning (e.g. storing corrected images for a vision model) — would require real training infrastructure, which isn't free. The text-based correction loop is the practical free alternative, with the limitation noted above.
