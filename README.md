# Kurdish Calorie Bot — Setup Guide (Gemini Free Tier)

Everything is already written. You just need two keys — both free — paste them in, and deploy. No coding required for launch.

## Why Gemini instead of Claude/OpenAI
- **Genuinely free, no credit card, no expiration.** Google AI Studio is the only major provider offering a permanent free API tier — OpenAI and Anthropic both require a card and give you a small expiring credit, not an ongoing free tier.
- **Free tier is enough for MVP validation.** `gemini-2.5-flash` gives a few hundred requests per day at no cost (exact number fluctuates — Google adjusts it periodically, check your limit live at ai.google.dev after signup). That's easily enough for testing with your Telegram community before any real launch.
- **Vision quality is strong and it's officially supported**, not a workaround — Gemini is Google's flagship multimodal model, actively maintained, with an official Python SDK.
- **No self-hosting, no GPU.** Same as before — it's a hosted API call, identical shape to what Claude was doing.

## What changed vs. the previous version
- `vision.py` now calls Google's Gemini API instead of Anthropic's — same function signature, same JSON output, same everything downstream. `bot.py`, `storage.py`, and `kurdish_foods.py` are **completely untouched**.
- `requirements.txt`: swapped `anthropic` for `google-genai`
- `.env.example`: `ANTHROPIC_API_KEY` → `GEMINI_API_KEY`
- No feature, no UX, no architecture changes. Same bot, same buttons, same macros, same Kurdish text.

## Step 1 — Get your Telegram bot token (5 minutes, unchanged)
1. Open Telegram, search for **@BotFather**.
2. Send `/newbot`, follow the prompts.
3. Copy the token it gives you.

## Step 2 — Get a free Gemini API key (2 minutes)
1. Go to **https://aistudio.google.com/apikey**
2. Sign in with any Google account (a personal Gmail account is fine).
3. Click **"Create API key"**.
4. Copy the key.

**Billing information required: none.** No credit card, no payment method, nothing to attach. This is the free tier by default — you would have to deliberately opt into a paid plan later if you outgrow it, it never auto-charges you.

One thing to know: on the free tier, Google's terms allow your prompts/images to be used to improve their models. For an MVP food-photo bot this is a non-issue, but worth knowing — if that ever matters to you (e.g. once you have real user data volume), the fix later is simply enabling billing on the same project, which switches you to the paid data-privacy terms without changing any code.

## Step 3 — Fill in your keys
1. Rename `.env.example` to `.env`
2. Paste both keys in.

## Step 4 — Deploy on Railway (same as before)
1. Create a free Railway account, connect it to GitHub.
2. Push this folder to a new GitHub repo (or upload the folder directly in Railway).
3. In Railway's project settings, add two environment variables: `TELEGRAM_BOT_TOKEN` and `GEMINI_API_KEY`.
4. Set the start command to: `python bot.py`
5. Deploy. Railway keeps it running 24/7.

(Render.com works identically if you prefer it.)

## Step 5 — Test it yourself first
1. Open your bot in Telegram, send `/start`.
2. Send 15–20 real photos of Kurdish meals you actually eat.
3. Note anything wrong — you'll fix it in Step 6.

## Step 6 — The only "real" work: improve the glossary
Open `kurdish_foods.py`. Plain list, no logic to touch:
```python
{
    "name": "دۆلمە",
    "aliases": ["Dolma", "stuffed grape leaves", "stuffed vegetables"],
    "kcal": 320, "protein_g": 12, "carbs_g": 40, "fat_g": 12,
},
```
Copy the shape, fill in a new dish, done. Run `python review_feedback.py` anytime to see what real users flagged 👎 "wrong" — that's your prioritized fix list.

⚠️ **Important, unchanged from before:** I'm not a native Kurdish speaker. Review every Kurdish string in `bot.py` and every dish name/alias in `kurdish_foods.py` before launch.

## Step 7 — Soft launch
Same as before: release to your Telegram community first, not TikTok, so real usage surfaces glossary gaps before a wider push.

## If you outgrow the free tier later
You'll know because you'll start seeing 429 errors (rate limit hit) in Railway's logs. At that point:
- Enabling billing on the same Google Cloud project raises your limits substantially and costs very little per request (a photo scan is a fraction of a cent)
- No code changes needed — same API key, same code, Google just raises your ceiling once billing is attached
- This is a "flip a switch later" decision, not something to worry about at MVP stage

## What to add later (not needed for launch)
- Telegram Stars paywall for premium features
- Migrate SQLite → Postgres if you pass a few thousand daily users
- Auto-suggest glossary entries from repeated 👎 feedback instead of reviewing manually
