# Kurdish Calorie Bot — Setup Guide (100% Free Stack)

Two free API keys, no credit card, no paid services anywhere in this project.

## Bug fix: circuit breaker feedback loop (this version)

**What you saw:** `/stats` showing 27 rate-limit errors, circuit breaker permanently active, pacing pinned at the 30s ceiling, queue empty.

**Root cause, confirmed and reproduced with a test:** the circuit breaker's own synthetic "busy" responses (returned when the circuit is open, *without ever contacting Gemini*) were being fed back into the same statistics that decide whether to keep the circuit open. Every short-circuited request looked exactly like "another confirmed 429" to the tracking logic - so once the circuit tripped, it could re-justify staying open off its own defensive output, indefinitely, regardless of whether Gemini itself had recovered. The `rate_limited_failures` counter in `/stats` was also conflating real Gemini responses with synthetic short-circuits, so "27" didn't necessarily mean 27 real 429s.

**Fix:** only real Gemini attempts now feed the adaptive-pacing/circuit-breaker stats (`gemini_queue.py`, `_worker`). Short-circuited requests are counted separately (`circuit_breaker_short_circuits`, now shown distinctly in `/stats`) and never touch the real failure counters. Reproduced the exact bug (tripped the circuit with 3 real failures, then fed it 10 synthetic short-circuits) and confirmed the real counters correctly stay at 3, not climb to 13.

**Also added:** exponential circuit-reopen backoff (60s → 120s → 240s → capped at 300s) for genuinely sustained failures, resetting the moment a real recovery probe succeeds. A burst-style rate limit clears in one 60s window; a truly exhausted daily/project quota won't, and probing every 60s for hours serves no purpose. Tested: confirmed cooldowns grow 0.2→0.4→0.8→capped in a scaled-down simulation, and confirmed a successful real probe resets everything (interval, consecutive-failure counter, reopen backoff) back to healthy.

**On your actual "is this a real quota exhaustion" question:** with the bug fixed, if you deploy this and *still* see sustained real `rate_limited_failures` climbing (not `circuit_breaker_short_circuits`), that's now a trustworthy signal of genuine Gemini-side exhaustion, not a code artifact. At that point:
- Check https://aistudio.google.com/apikey confirms your key is still active and matches Railway's `GEMINI_API_KEY` env var exactly (a silently-regenerated or mismatched key typically shows as 401/403, not 429, but worth ruling out first).
- Check your actual current limits and usage at https://ai.google.dev/gemini-api/docs/rate-limits - Google has cut free-tier limits before without much notice, and there's a separate daily (RPD) cap in addition to the per-minute one; sustained 429s across many minutes (not just a burst) point to RPD, not RPM.
- If RPD is exhausted, the only real fix is waiting for the daily reset (or, if you're past validating the MVP, enabling billing on the same project - the code needs zero changes for that, per the earlier Gemini setup notes below).

## Long-term scalability review (previous version)


The core constraint that shapes everything below: Gemini's free-tier RPM (~7-9/min at our conservative pacing) is a hard ceiling no code change increases. So the real goal isn't "handle thousands of *simultaneous* analyses" — it's *never waste a request, degrade gracefully under backlog, and stay memory-safe while queued*. Everything here is filtered through that.

**Implemented (genuine, measured impact):**
- **Image optimization moved before the queue, not inside the worker.** A backlog used to mean megabytes of full-size phone photos sitting in memory per queued job. Now the queue only ever holds the ~30-50KB optimized version.
- **Adaptive pacing (AIMD)** replaces the fixed 7s guess. Backs off hard (×1.6) the instant a real 429 happens; cautiously eases down (−0.25s) after 6 consecutive clean successes, floor 5s / ceiling 30s. Tested: confirmed it speeds up under sustained health and snaps back on real rate-limit evidence.
- **Circuit breaker**: after 3 consecutive rate-limited failures, opens for 60s and every queued job gets an instant honest "busy" response instead of each one separately burning ~90s on a doomed retry cycle. Tested: confirmed zero Gemini calls happen while the circuit is open, and it recovers automatically after cooldown.
- **DB indexes** on `meals(user_id, created_at)` and a partial index on `feedback`. Verified with `EXPLAIN QUERY PLAN` that SQLite actually uses them, not just that they exist. Every `/today`/`/week`/`/history` query hits this.
- **Defensive worker loop**: an unexpected exception anywhere in a job (not just classified API errors) used to have a theoretical path to silently killing the entire background worker - permanent outage until a manual restart. Tested by injecting a raw `RuntimeError` mid-analysis and confirming the worker survives and keeps processing the next job.
- **Queue depth cap** (40): beyond this, new submissions fail fast with a "very busy" message instead of queuing into a wait time of tens of minutes.
- **`/stats` command**: real observability - total requests, cache hit rate, current adaptive interval, circuit breaker state, queue depth. Not gated by any admin check (this app has no auth concept); restrict it later by checking `update.effective_user.id` if you want.
- **Cache bumped 200 → 500 entries**, and stale per-user cooldown entries get swept periodically - both cheap, bound memory more tightly under long-term growth.

**Considered and explicitly rejected (explained, not just skipped):**
- **Perceptual/near-duplicate image hashing** - real risk (two different dishes falsely matching as "similar enough" would silently serve wrong nutrition data) against a low expected benefit (people rarely re-photograph the exact same plate for this kind of app). Not worth it.
- **Migrating off SQLite** - Gemini's RPM ceiling is 1-2 orders of magnitude below anything SQLite+WAL can handle; it will never be the actual bottleneck.
- **A persistent/durable job queue surviving restarts** - the real queue is rarely more than a handful of jobs deep given the RPM ceiling; not worth the engineering effort to protect a rare, low-cost event.
- **SQLite connection pooling** - per-call overhead (~1ms) is noise next to the multi-second Gemini pacing dominating the critical path.
- **Downscaling images below 1024px** - would save a little more bandwidth at real risk to recognition accuracy.
- **Redis or an external queue/cache service** - reintroduces a paid dependency for no benefit at this scale.

## Scalability & reliability update (previous version)

**Root issue diagnosed:** Google cut Gemini's free-tier rate limits significantly in recent months - some tiers are down to single-digit requests per minute. The bot's own logic was healthy; nothing was calling Gemini more than once per photo. The 429s were real quota pressure, not a bug in the analysis code.

**What changed, and why each piece matters:**

1. **Verified single-request-per-photo** — confirmed by code inspection and an automated test: exactly one call site (`gemini_queue.submit_photo_job`) is reachable from `handle_photo`, and `estimate_calories`'s internal retry loop only fires on an actual failure, never duplicates a successful call.
2. **`gemini_queue.py` (new file)** — a single background worker processes all photos sequentially with an enforced minimum gap between real Gemini calls (`MIN_SECONDS_BETWEEN_REQUESTS`, default 7s ≈ 8-9 req/min). This is the actual fix for burst 429s: no matter how many users upload at once, requests leave at a safe, steady pace instead of firing all at once. **This is the single most important tunable in the whole update** — if you still see `[RATE_LIMIT]` in your Railway logs after deploying, raise this number. Check your current real limit at https://ai.google.dev/gemini-api/docs/rate-limits, since Google has changed it before without much notice.
3. **Retry logic in `vision.py`** — the google-genai SDK's own built-in retry is disabled (it has a known bug where it ignores the server's suggested retry delay). Our own loop retries up to 4 times on 429/500/502/503/504/timeouts with exponential backoff, and parses the server's suggested wait time out of the error message when present. Non-retryable errors (400/403/404 — bad key, bad request) fail immediately instead of wasting attempts.
4. **Two different failure messages** — a rate-limit exhaustion now shows the Kurdish "بۆتەکە زۆر بەکاردەهێنرێت" message instead of the generic "check your photo" tips, since the two situations need different user reactions.
5. **Per-user cooldown** (`gemini_queue.check_user_cooldown`, default 8s) — checked *before* a photo even enters the queue, so one user spamming photos can't consume quota that other users are waiting on.
6. **Duplicate-image cache** — every photo is hashed (SHA-256); an identical photo analyzed within the last hour returns the cached result instantly with zero Gemini calls. Useful for accidental double-sends and repeat photos.
7. **Image optimization** (`vision.optimize_image`, needs the new `Pillow` dependency) — resizes to 1024px on the long side at JPEG quality 85 before upload. Tested against a realistic phone-photo-sized image: meaningfully smaller upload with no loss to recognition quality, since 1024px is well above what's needed to identify food and read portions.
8. **Structured logging** — every failure path now logs a clear tag: `[RATE_LIMIT]`, `[SERVER_ERROR]`, `[TIMEOUT]`, `[JSON_PARSE]`, `[SDK_ERROR]`, `[UNEXPECTED]`, `[QUEUE]`, `[CACHE]`, `[IMAGE_OPTIMIZE]`. Searching Railway logs for any of these tags should make debugging take minutes, not hours.
9. **Failed requests were already never saved** — verified this was already correct (only the `status == "ok"` branch calls `storage.log_meal`), and added an automated test to lock in that guarantee going forward.
10. **Additional free optimizations found in review:**
    - **The blocking Gemini call now runs via `asyncio.to_thread`** inside the queue worker — this was a real (if invisible) bug before: `client.models.generate_content()` is a synchronous/blocking call, and calling it directly inside an `async def` handler froze the *entire bot* (all users, all commands) for the duration of every single photo analysis. This was arguably a bigger scalability problem than the 429s themselves.
    - **SQLite WAL mode** enabled (`storage.py`) — lets reads and writes happen concurrently instead of blocking each other under multiple simultaneous users. One line, no downside.
    - **Corrections prompt already capped at 60 entries** (pre-existing) — confirmed this stays bounded as your correction count grows, so prompt size/token cost doesn't creep up unbounded over time.

**What I deliberately did NOT change:** recognition prompt logic, glossary, macro calculations, or anything user-facing about the analysis itself — this update is purely about *reliability of delivery*, not accuracy.

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
- `gemini_queue.py` — request pacing, per-user cooldown, and duplicate-image caching (see the scalability section above).
- **One new dependency**: `Pillow` (image resizing) — still fully free/open-source, added to `requirements.txt`. Redeploying on Railway will pick it up automatically.

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
