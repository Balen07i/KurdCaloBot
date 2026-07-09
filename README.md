# Kurdish Calorie Bot — Setup Guide (Gemini Free Tier)

Everything is already written. You just need two keys — both free — paste them in, and deploy. No coding required for launch.

## What this bot does now
1. User sends a photo of food to your Telegram bot.
2. Gemini identifies **every distinct food on the plate separately** (not just one item), estimates each one's portion size, and calculates calories + protein + carbs + fat for each — then a total.
3. The bot replies in natural, everyday Sorani Kurdish: each food's numbers, a total (when there's more than one item), a confidence level with a one-sentence explanation, and one short personalized nutrition tip specific to that meal.
4. Every result has 👍/👎 buttons so users can flag wrong estimates.
5. `/today` and `/week` show running totals including macros.

## Reliability fixes (this update)
- **Root cause of the "Unknown / 0 kcal" bug found and fixed**: `gemini-2.5-flash` spends part of its output token budget on internal "thinking" before writing the answer. The old `max_output_tokens=800` wasn't enough headroom, so on some photos the JSON got cut off mid-way, failed to parse, and silently fell back to a fake "Unknown, 0 kcal" result — indistinguishable from a real answer. Fixed by raising the token budget, explicitly capping the thinking budget, and adding a one-time automatic retry with a stricter prompt if parsing still fails.
- **Three distinct outcomes now, not one fallback**: a real result, a genuine "no food visible" message, or a "couldn't analyze — try a clearer photo" message with concrete tips (lighting, whole plate, less blur, less zoom). Only real results get logged to your totals.
- **Tolerant JSON parsing**: handles markdown-fenced responses and stray text before/after the JSON, not just perfectly clean output.
- **Fuzzy glossary matching in code** (`kurdish_foods.find_glossary_match`), independent of the model's own judgment — catches things like "Grilled chicken" matching your "مریشکی برژاو" entry even when Gemini doesn't word it exactly the same way, and relabels it with your canonical name/emoji.
- **Confidence is now scoped correctly**: the prompt explicitly says item count is never itself a reason for lower confidence — only image clarity, visibility, and identification/portion certainty are.
- **`requirements.txt`** bumped `google-genai` to `>=1.0.0` — the thinking-budget feature had known instability in earlier SDK versions.

## What changed in this polish pass
- **Multi-food detection**: one photo with several dishes now gets each item identified, portioned, and calculated separately, with a total at the end.
- **Natural Kurdish everywhere**: every UI string and every AI-generated sentence is now written (and prompted for) as everyday spoken Sorani, not literal/machine-translated phrasing.
- **Personalized insight**: one short, non-repetitive nutrition tip per meal, generated to match what was actually detected — not a generic canned line.
- **Cleaner food names**: no more "(English)" clutter — just the Kurdish name and a matching emoji, reused consistently from the glossary.
- **Confidence is explained, not just labeled**: a short Kurdish sentence says *why* confidence is high or low (image clarity, ambiguous portion, dish not in the glossary, etc).
- **Database migration is automatic and safe**: `storage.py` adds the new columns needed for multi-food data with `ALTER TABLE` on startup, so this deploys cleanly on top of your already-running Railway database without losing any existing history.

## Why Gemini instead of Claude/OpenAI (unchanged reasoning)
- **Genuinely free, no credit card, no expiration.** Google AI Studio is the only major provider offering a permanent free API tier.
- **Free tier is enough for MVP validation.** `gemini-2.5-flash` gives a few hundred requests per day at no cost (exact number fluctuates — check your live limit at ai.google.dev after signup).
- **Officially supported**, not a workaround — Google's flagship multimodal model with an official Python SDK.
- **No self-hosting, no GPU** — same hosted API-call shape as before.

## Step 1 — Get your Telegram bot token (unchanged)
1. Open Telegram, search for **@BotFather**.
2. Send `/newbot`, follow the prompts.
3. Copy the token it gives you.

## Step 2 — Get a free Gemini API key (unchanged)
1. Go to **https://aistudio.google.com/apikey**
2. Sign in with any Google account.
3. Click **"Create API key"**.
4. Copy the key.

**Billing information required: none.** No credit card, no payment method. Free by default; you'd have to deliberately enable billing later to ever be charged.

## Step 3 — Fill in your keys
1. Rename `.env.example` to `.env`
2. Paste both keys in.

## Step 4 — Deploy on Railway (unchanged)
1. Push this folder to GitHub (or upload directly to Railway).
2. Add the two environment variables: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`.
3. Start command: `python bot.py`
4. Deploy.

Since you're updating an **already-deployed** bot: just push this new code the same way you deployed the first time (redeploy on Railway). The database migration is automatic — no manual DB steps, no data loss.

## Step 5 — Test it yourself first
1. Send `/start`.
2. Send 15–20 real photos, including a few plates with **more than one food item** on them, to test the new multi-food detection.
3. Note anything wrong — you'll fix it in Step 6.

## Step 6 — The only "real" work: improve the glossary
Open `kurdish_foods.py`. Plain list, no logic to touch:
```python
{
    "name": "دۆلمە", "emoji": "🫑",
    "aliases": ["Dolma", "stuffed grape leaves", "stuffed vegetables"],
    "kcal": 320, "protein_g": 12, "carbs_g": 40, "fat_g": 12,
},
```
Copy the shape, fill in a new dish, done. Run `python review_feedback.py` anytime to see what real users flagged 👎 "wrong", now including full multi-food detail per flagged result.

⚠️ **Important, still true:** I'm not a native Kurdish speaker. I wrote every string here in natural, everyday Sorani to the best of my ability and prompted Gemini to do the same for its generated text — but please read through `bot.py`'s messages, `vision.py`'s prompt, and `kurdish_foods.py`'s names/aliases before launch, and correct anything that doesn't sound right to you as a native speaker. This is the one part no AI can fully verify.

## Step 7 — Soft launch
Same as before: release to your Telegram community first, so real usage surfaces glossary gaps before a wider push.

## If you outgrow the free tier later
You'll see 429 errors in Railway's logs. Enabling billing on the same Google Cloud project raises your limits with no code changes — a "flip a switch later" decision, not an MVP concern.

## What to add later (not needed for launch)
- Telegram Stars paywall for premium features
- Migrate SQLite → Postgres if you pass a few thousand daily users
- Auto-suggest glossary entries from repeated 👎 feedback instead of reviewing manually
