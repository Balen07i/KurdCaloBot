# vision.py
#
# Sends a food photo + the Kurdish dish glossary (+ any learned user
# corrections) to Gemini's vision API and parses back a structured,
# multi-food calorie + macro estimate, plus a short personalized Kurdish
# nutrition insight.
#
# Uses Google's free Gemini API tier - no paid service anywhere in here.
#
# RESILIENCE NOTE: the google-genai SDK has its own built-in retry, but it
# has a known bug (as of writing) where it ignores the server's suggested
# retry-after delay and just uses fixed backoff - which wastes retries
# under real rate-limit pressure. We disable the SDK's built-in retry
# (attempts=1) and do our own below, so we have full control over backoff,
# Retry-After handling, and logging.

import hashlib
import io
import json
import logging
import os
import re
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from kurdish_foods import build_confusable_prompt, build_glossary_prompt, find_glossary_match

logger = logging.getLogger(__name__)

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=1),  # we handle retries ourselves
        timeout=45_000,  # ms - without this, a hung Gemini call blocks the ENTIRE
        # single-worker queue forever (every other queued user too), with
        # no backoff/circuit-breaker recovery possible since nothing ever
        # comes back to classify. 45s is generous above normal response
        # times but bounds the worst case.
    ),
)

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# Flash-Lite (gemini-2.5-flash-lite) has ~4x the free-tier daily quota and
# is significantly cheaper if you go paid later. Set GEMINI_MODEL=gemini-2.5-flash-lite
# in Railway to test it - swap back by unsetting the var.

# --- A/B testing infrastructure ---------------------------------------
#
# I can't call the live Gemini API from this environment to benchmark
# Flash vs Flash-Lite myself, so instead of guessing, this collects real
# comparative production data automatically. Set AB_TEST_MODEL to a
# candidate model and AB_TEST_PERCENTAGE (0-100) to route that fraction
# of USERS to it - split is deterministic per user_id (same user always
# gets the same model), so comparisons aren't confounded by one user's
# meals being split across both. Every meal logs which model produced it
# (see storage.log_meal's model_used column), and /stats breaks down
# confidence/correction rate by model - that's the real A/B data.
AB_TEST_MODEL = os.environ.get("AB_TEST_MODEL", "")
AB_TEST_PERCENTAGE = int(os.environ.get("AB_TEST_PERCENTAGE", "0"))


def pick_model_for_user(user_id: int) -> str:
    """Deterministic per-user split - stable across that user's requests."""
    if not AB_TEST_MODEL or AB_TEST_PERCENTAGE <= 0:
        return MODEL_NAME
    if AB_TEST_PERCENTAGE >= 100:
        return AB_TEST_MODEL
    bucket = int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 100
    return AB_TEST_MODEL if bucket < AB_TEST_PERCENTAGE else MODEL_NAME

# IMPORTANT: gemini-2.5-flash spends part of max_output_tokens on internal
# "thinking" before it writes the final answer. Too small a budget was the
# root cause of a real bug where JSON got truncated mid-way and silently
# fell back to a fake "Unknown / 0 kcal" result. thinking_budget caps how
# much of the budget thinking can eat; max_output_tokens leaves generous
# room for the JSON itself on top of that.
THINKING_BUDGET = 1200
MAX_OUTPUT_TOKENS = 3500

# Retry tuning. RETRYABLE_STATUS_CODES per Google's own troubleshooting
# guidance (429 rate limit, 408/500/502/503/504 transient server issues).
# 400/401/403/404 are NOT retried - those mean something is wrong with the
# request itself (bad key, bad payload) and retrying won't help.
#
# IMPORTANT (fixes a real production bug): Gemini's 429 error message can
# suggest a retry delay far longer than a per-minute limit would imply -
# under sustained free-tier pressure it can legitimately say "retry in
# 400+ seconds" (e.g. a daily-quota-style reset, not a burst limit). If we
# blindly slept for that full duration, one unlucky photo could block the
# single worker (and therefore every user queued behind it) for many
# minutes. MAX_BACKOFF_SECONDS below is a hard ceiling applied to BOTH
# our own exponential backoff AND any server-suggested delay - we would
# rather fail fast with a clear "try again shortly" message than make
# someone stare at "🔍 analyzing..." for 7 minutes. Worst case total time
# for one photo: MAX_ATTEMPTS-1 retry gaps × MAX_BACKOFF_SECONDS ≈ 90s,
# not minutes.
MAX_ATTEMPTS = 4
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
BASE_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 30.0

# Image optimization: shrinks upload size and vision-token cost without a
# meaningful accuracy loss - 1024px on the long side is well above what's
# needed to identify food/portions, and 85% JPEG quality is visually
# lossless for this purpose.
MAX_IMAGE_DIMENSION = 1024
JPEG_QUALITY = 85

INSIGHT_STYLE_EXAMPLES = """\
- 💪 ئەم خواردنە سەرچاوەیەکی باشی پرۆتینە.
- 🥗 زیادکردنی سەوزە فایبەری خواردنەکەت زیاد دەکات.
- 🔥 بۆ کێش زیادکردن زۆر گونجاوە.
- ⚖️ ئەگەر ئامانجت کەمکردنەوەی کێشە، واباشە قەبارەی برنج کەمتر بێت.
- 💧 بیرت نەچێت لەگەڵ ئەم خواردنە ئاوی تەواو بخۆیت."""


def optimize_image(image_bytes: bytes) -> bytes:
    """
    Resizes to a max 1024px on the long side and re-encodes as JPEG q85.
    Falls back to the original bytes if Pillow can't process it for any
    reason (never block a scan over an optimization failure).
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        longest_side = max(img.size)
        if longest_side > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / longest_side
            new_size = (round(img.width * scale), round(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buffer.getvalue()
    except Exception:
        logger.exception("[IMAGE_OPTIMIZE] Failed to optimize image, using original")
        return image_bytes


# --- Local pre-filter (catches obvious junk before it ever costs a request) --
#
# Deliberately conservative: only rejects images that are near-certain to
# fail analysis anyway (solid-color frames, near-total-black captures).
# Never tries to judge "is this food" - that's Gemini's job, and a wrong
# local rejection of a valid photo is worse than one wasted request. Pure
# Pillow, no new dependency, sub-millisecond on an already-optimized image.
MIN_PIXEL_STDDEV = 5.0     # near-uniform/blank frame if variance is this low
MIN_MEAN_BRIGHTNESS = 8.0  # near-total-black frame (0-255 scale)
MIN_DIMENSION_PX = 80


def check_image_locally(image_bytes: bytes) -> tuple[bool, str]:
    """
    Returns (is_valid, reason_if_invalid). reason_if_invalid is a short
    natural Kurdish sentence suitable for showing directly to the user.
    Fails open (treats as valid) on any processing error - if we can't
    tell, let Gemini decide rather than block a legitimate photo.
    """
    try:
        from PIL import Image, ImageStat

        img = Image.open(io.BytesIO(image_bytes))
        if min(img.size) < MIN_DIMENSION_PX:
            return False, "📷 وێنەکە زۆر بچووکە. تکایە وێنەیەکی ئاساییی خواردنەکە بنێرە."

        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        stddev = stat.stddev[0]
        mean = stat.mean[0]

        if stddev < MIN_PIXEL_STDDEV:
            return False, "📷 وێنەکە دیار نییە (تەنها ڕەنگێکی ساف). تکایە دووبارە وێنە بگرە."
        if mean < MIN_MEAN_BRIGHTNESS:
            return False, "📷 وێنەکە زۆر تاریکە. تکایە لە شوێنێکی ڕووناکتر وێنە بگرە."

        return True, ""
    except Exception:
        logger.exception("[LOCAL_PREFILTER] Failed to check image, letting it through")
        return True, ""


# --- Conservative perceptual hash (near-duplicate detection) -----------
#
# A plain 64-bit dHash (difference hash), hand-rolled with only Pillow -
# no new dependency. Used ONLY with a strict Hamming-distance threshold
# (see gemini_queue.PHASH_HAMMING_THRESHOLD) specifically to catch the
# real, narrow scenario of someone resending essentially the same photo
# after it's been re-compressed by forwarding/screenshotting (which
# breaks exact SHA-256 matching but not this). Deliberately NOT used for
# loose "similar-looking food" matching - that's a real accuracy risk for
# a personal meal-tracking bot, evaluated and rejected (see README).
def compute_dhash(image_bytes: bytes) -> int | None:
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((9, 8), Image.LANCZOS)
        pixels = list(img.getdata())
        bits = 0
        for row in range(8):
            for col in range(8):
                left = pixels[row * 9 + col]
                right = pixels[row * 9 + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
        return bits
    except Exception:
        logger.exception("[PHASH] Failed to compute dHash")
        return None


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# --- Local pre-filter (zero Gemini calls) --------------------------------
#
# Deliberately conservative: only rejects images that are essentially
# guaranteed to be worthless (near-blank, near-black, degenerate frames).
# A full "is this actually food" classifier was considered and rejected -
# false-negative risk (wrongly rejecting a valid food photo) is worse than
# one avoidable Gemini call, so we only catch the unambiguous cases here
# and let Gemini's own no_food_detected handle everything else.
MIN_PIXEL_STDDEV = 5.0     # near-uniform/blank frame
MIN_MEAN_BRIGHTNESS = 8.0  # near-total-black frame (not just "dim")
MIN_DIMENSION_PX = 80


def check_locally_invalid(image_bytes: bytes) -> str | None:
    """
    Returns a short reason string if the image is obviously unusable
    (skip Gemini entirely), or None if it should proceed normally.
    Cheap (a few ms) - runs on the already-optimized, smaller image.
    """
    try:
        from PIL import Image, ImageStat

        img = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale

        if min(img.size) < MIN_DIMENSION_PX:
            return "too_small"

        stat = ImageStat.Stat(img)
        stddev = stat.stddev[0]
        mean = stat.mean[0]

        if stddev < MIN_PIXEL_STDDEV:
            return "blank_or_uniform"
        if mean < MIN_MEAN_BRIGHTNESS:
            return "too_dark"

        return None
    except Exception:
        logger.exception("[PREFILTER] Failed to inspect image, letting it through")
        return None  # never block a scan over a prefilter bug


# --- Lightweight perceptual hash (dHash) ---------------------------------
#
# Pure Pillow, no new dependency. Deliberately used with a STRICT Hamming
# distance threshold (see gemini_queue.py) - this catches near-identical
# recompressed/forwarded copies of the same photo, not "visually similar
# but different" dishes. A looser threshold was evaluated and rejected:
# two different rice-and-stew dishes can have similar color/texture
# distribution, and a false match would silently serve wrong nutrition
# data, which is worse than the (small) quota cost of a cache miss.
def compute_dhash(image_bytes: bytes, hash_size: int = 8) -> int | None:
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        img = img.resize((hash_size + 1, hash_size), Image.LANCZOS)
        pixels = list(img.getdata())

        bits = 0
        for row in range(hash_size):
            row_start = row * (hash_size + 1)
            for col in range(hash_size):
                bits <<= 1
                if pixels[row_start + col] > pixels[row_start + col + 1]:
                    bits |= 1
        return bits
    except Exception:
        logger.exception("[DHASH] Failed to compute perceptual hash")
        return None


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _build_corrections_prompt(corrections: list[dict]) -> str:
    """
    Folds in real user corrections as extra glossary-like context. This is
    the whole "learning" loop: a mistake fixed once by any user quietly
    improves recognition for everyone afterward, at zero extra cost -
    it's just more text in the same prompt, no retraining, no new service.
    """
    if not corrections:
        return ""
    lines = [
        f"- If something looks like \"{c['wrong_name']}\", a real user "
        f"corrected this before to: {c['correct_name_kurdish']}"
        for c in corrections[:60]  # keep the prompt bounded
    ]
    return (
        "\n\nReal corrections submitted by users - treat these as reliable "
        "signal, they've been confirmed by a human:\n" + "\n".join(lines)
    )


def _build_system_prompt(corrections: list[dict]) -> str:
    return f"""You are a friendly nutrition-tracking assistant for a Kurdish \
(Sorani) audience in the Kurdistan Region. You will be shown a photo of a meal \
that may contain one or several different foods on the same plate or table.

{build_glossary_prompt()}

{build_confusable_prompt()}
{_build_corrections_prompt(corrections)}

REASON IN THIS ORDER (internally - only the final JSON is shown to the user):
1. Identify: scan the whole image and list every distinct FOOD item - \
including drinks, sauces, oils, bread, sides, and garnishes, not just the \
main dish. Ignore plates, bowls, cups, cutlery, napkins, hands, tables, and \
background objects - those are not foods. Never invent an ingredient you \
cannot reasonably see (e.g. don't assume butter or oil was used unless \
there's visible sheen/pooling, don't assume a sauce is present unless you \
can actually see it). If two foods are touching or slightly overlapping, \
list them as separate items - never merge different foods into one entry.
2. Verify: before finalizing your list, check each item against the photo \
one more time - could you point to the exact pixels showing this food? \
Foods get added by habit/expectation (e.g. assuming bread accompanies a \
meal because it usually does) even when not actually visible - if you \
can't clearly justify an item from what's actually in the photo, remove \
it. A shorter, accurate list is always better than a complete-feeling but \
partly invented one.
3. Portion: for EACH food, estimate its portion using whichever unit fits \
best (grams, pieces/دانە, cups/کاسە, slices/پارچە). Use visible reference \
objects to judge scale - a standard dinner plate is ~25-28cm across, a \
tablespoon holds ~15ml, a person's palm is roughly one portion of meat, a \
teacup is ~200ml. Compare the food to whatever reference objects (plate, \
bowl, spoon, fork, hand, cup) are actually visible in the photo. For food \
that's mixed, stacked, or spread across the plate, estimate volume by \
visualizing it separated out, not just by its 2D footprint in the photo.
4. Nutrition: for EACH food, calculate calories, protein, carbs, and fat \
scaled to that estimated portion, and factor in the visible cooking method \
(grilled/fried/boiled/raw change fat content significantly) and any oils, \
butter, ghee, or sauces you can ACTUALLY see evidence of - never add these \
by default "just in case".
5. Only after steps 1-4 are done for every item, produce the final JSON.

BRAND RECOGNITION: if a packaged/branded product is visible and its name \
is legible on the packaging or logo, use the actual product name (e.g. \
"Ülker Biskrem") instead of a generic description ("chocolate cream \
biscuit") - this is both more useful to the user and more nutritionally \
accurate, since branded products have a real, specific nutrition profile \
rather than a generic estimate. Keep the brand name as written, don't \
translate it.

RECOGNIZING COMMON STAPLES - be decisive, not cautious:
Rice, bread, grilled or stewed meat, chicken, fish, eggs, milk/yogurt, \
fruit, and vegetables are everyday foods that are usually easy to recognize \
even in an imperfect photo. If any of these (or anything else reasonably \
identifiable) is visible, you MUST attempt a real estimate. Only use \
"no food detected" when the photo genuinely shows no food at all.

HANDLING DIFFICULT PHOTOS:
Low light, partial plates, close-up crops, mild blur, or mixed/overlapping \
meals should NOT stop you from estimating - they should lower your \
confidence instead, with a short honest note about what made it harder.

CONFIDENCE RULES:
Base confidence ONLY on: image clarity/lighting, how clearly each food is \
visible, how certain the identification is, and how visible the portion is. \
The NUMBER OF FOOD ITEMS is never itself a reason to lower confidence.

UNCERTAIN IDENTIFICATION - be honest, not confidently wrong:
If you cannot confidently identify a SPECIFIC food (not the confusable-pair \
case below, just general uncertainty - e.g. an unfamiliar stew, a dish \
partly hidden by another, a sauce you don't recognize), do NOT invent a \
specific dish name to sound complete. Instead, use an honest general label \
(e.g. "خواردنێکی نەناسراو" / "stew, exact dish unclear") and set that food's \
contribution to "نزم" confidence overall, with note_kurdish explaining what \
made it hard to identify. A vague-but-honest label beats a specific-but-\
invented one - the user can always correct it, but a confident wrong guess \
teaches them nothing and may be trusted at face value.

GENUINE AMBIGUITY - use "alternatives", not a guess:
If (and ONLY if) you genuinely cannot tell apart two visually similar foods \
(see the confusable pairs above) even after looking carefully, do NOT \
silently pick one. Instead, keep your best single guess as the main \
"foods"/totals, but ALSO fill "alternatives" with 1-2 other plausible \
readings, each with what the total_kcal would be under that reading and a \
short explanation of the visual ambiguity. If you ARE reasonably confident, \
leave "alternatives" as an empty list - don't manufacture uncertainty that \
isn't there.

FOOD MATCHING:
Match foods to the glossary by meaning, not exact wording (e.g. "grilled \
chicken" should match a glossary chicken entry even worded differently). \
When matched, reuse the glossary's exact Kurdish name and emoji.

LANGUAGE RULES:
- Every piece of Kurdish text must be natural, everyday spoken Sorani \
Kurdish as used in the Kurdistan Region - never a stiff or literal \
translation. Keep terminology (کالۆری, پرۆتین, کاربۆهایدرەیت, چەوری) \
consistent.
- Do not attach English names to food unless there is genuinely no common \
Kurdish name for it.
- Prefer the authentic local Kurdish dish name over a generic or \
international-sounding translation whenever a real local name exists - \
e.g. use the actual Kurdish name for a traditional dish rather than a \
generic "rice with meat"-style description. The glossary above reflects \
this - reuse its names and aliases rather than inventing a more generic \
alternative.
- The one exception to writing in Kurdish is a recognized brand name (see \
BRAND RECOGNITION above) - keep those exactly as printed on the package.

Write ONE short, natural, non-judgmental nutrition insight in Kurdish \
specific to what was actually detected - not a generic tip. Match this \
tone and length (write a NEW sentence, don't copy these):
{INSIGHT_STYLE_EXAMPLES}

Respond ONLY with a JSON object, no other text, no markdown fences, in this \
exact shape:
{{
  "no_food_detected": true or false,
  "foods": [
    {{
      "name_kurdish": "...", "emoji": "🍚", "portion_kurdish": "...",
      "kcal": integer, "protein_g": integer, "carbs_g": integer, "fat_g": integer,
      "matched_glossary": true or false
    }}
  ],
  "total_kcal": integer, "total_protein_g": integer,
  "total_carbs_g": integer, "total_fat_g": integer,
  "confidence": "بەرز" | "مامناوەند" | "نزم",
  "note_kurdish": "one short sentence",
  "insight_kurdish": "one short sentence, starting with a fitting emoji",
  "alternatives": [
    {{
      "scenario_kurdish": "e.g. ئەگەر سرکەی هەنار بێت",
      "total_kcal": integer,
      "explanation_kurdish": "one short sentence on why this is uncertain"
    }}
  ]
}}

If no_food_detected is true, "foods" must be empty and other numeric fields \
must be 0. "alternatives" must be an empty list unless there's genuine \
visual ambiguity as described above. Macro rule: kcal ≈ protein_g*4 + \
carbs_g*4 + fat_g*9 (rough ballpark). Totals must equal the sum of all items."""


def _call_gemini(image_bytes: bytes, media_type: str, strict: bool, corrections: list[dict], model: str = MODEL_NAME) -> str:
    prompt_text = "Analyze every food in this meal photo."
    if strict:
        prompt_text += (
            " Your previous response was not valid JSON. Respond with "
            "ONLY the JSON object described in your instructions - no "
            "markdown fences, no commentary, nothing before or after it."
        )

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=media_type),
            prompt_text,
        ],
        config=types.GenerateContentConfig(
            system_instruction=_build_system_prompt(corrections),
            response_mime_type="application/json",
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
        ),
    )
    return response.text or ""


def _extract_json(raw_text: str):
    """Tolerant JSON extraction: handles clean JSON, markdown-fenced JSON,
    and JSON with stray text before/after it."""
    text = raw_text.strip()
    if not text:
        return None

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


_RETRY_AFTER_PATTERN = re.compile(r"retry in (\d+(?:\.\d+)?)s", re.IGNORECASE)


def _extract_retry_after_seconds(exc: Exception) -> float | None:
    """
    The google-genai SDK doesn't cleanly expose the server's suggested
    retry delay as a structured field, but 429 error messages usually
    contain it as text (e.g. "...Please retry in 53.0s."). Best-effort
    extraction from the message; falls back to None (caller uses
    exponential backoff instead) if it's not present.
    """
    match = _RETRY_AFTER_PATTERN.search(str(exc))
    if match:
        return float(match.group(1))
    return None


def _classify_and_log(exc: Exception, attempt: int) -> tuple[bool, float | None]:
    """
    Logs the failure with a clear, grep-able tag and returns
    (is_retryable, suggested_wait_seconds).
    """
    if isinstance(exc, genai_errors.APIError):
        code = exc.code
        if code == 429:
            wait = _extract_retry_after_seconds(exc)
            logger.warning(
                "[RATE_LIMIT] Gemini 429 on attempt %d, server suggests %s "
                "(capped to %.0fs max before use): %s",
                attempt, f"{wait}s" if wait else "no delay given", MAX_BACKOFF_SECONDS, exc,
            )
            return True, wait
        if code in RETRYABLE_STATUS_CODES:
            logger.warning("[SERVER_ERROR] Gemini %d on attempt %d: %s", code, attempt, exc)
            return True, None
        logger.error("[SDK_ERROR] Non-retryable Gemini error %s on attempt %d: %s", code, attempt, exc)
        return False, None

    if isinstance(exc, (TimeoutError, ConnectionError)):
        logger.warning("[TIMEOUT] Network timeout/connection error on attempt %d: %s", attempt, exc)
        return True, None

    logger.exception("[UNEXPECTED] Unhandled exception on attempt %d", attempt)
    return True, None  # unknown errors get one benefit-of-the-doubt retry cycle


def estimate_calories(
    image_bytes: bytes, media_type: str = "image/jpeg", corrections: list[dict] | None = None,
    model: str = MODEL_NAME,
) -> dict:
    """
    Makes EXACTLY ONE logical analysis per call (retries below are for
    resilience against transient failures, not duplicate work - a photo
    that succeeds on attempt 1 never triggers attempt 2).

    NOTE: expects image_bytes to already be optimized (see optimize_image
    below) - the caller (gemini_queue.submit_photo_job's caller) should
    call optimize_image() BEFORE this, and ideally before even enqueueing,
    so the queue never holds full-size originals under a backlog.

    Returns a dict with a "status" key:
      - "ok": normal result (see _finalize_result for full shape). Also
        includes "model_used" for A/B attribution.
      - "no_food": Gemini determined the photo genuinely has no food
      - "failed": technical failure. Includes a "reason":
          - "rate_limited": all retries exhausted while being rate-limited
            - caller should show the "bot is busy" message, not tips
          - "other": non-rate-limit failure - caller should show photo tips
    """
    corrections = corrections or []
    parsed = None
    last_failure_was_rate_limit = False

    for attempt in range(1, MAX_ATTEMPTS + 1):
        strict = attempt > 1  # ask more firmly for clean JSON after the first miss
        try:
            raw_text = _call_gemini(image_bytes, media_type, strict, corrections, model=model)
        except Exception as exc:
            is_retryable, suggested_wait = _classify_and_log(exc, attempt)
            last_failure_was_rate_limit = isinstance(exc, genai_errors.APIError) and exc.code == 429

            if not is_retryable or attempt == MAX_ATTEMPTS:
                break

            # THE FIX: cap suggested_wait too, not just our own computed
            # backoff - a server-suggested delay is honored up to the same
            # ceiling, never blindly trusted for its full duration.
            computed_backoff = min(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)
            wait = min(suggested_wait, MAX_BACKOFF_SECONDS) if suggested_wait else computed_backoff
            time.sleep(wait)
            continue

        parsed = _extract_json(raw_text)
        if parsed is not None:
            break

        logger.warning("[JSON_PARSE] Could not parse Gemini response on attempt %d: %.200s", attempt, raw_text)
        if attempt < MAX_ATTEMPTS:
            time.sleep(1)  # brief pause before the stricter retry, not rate-limit related

    if parsed is None:
        return {"status": "failed", "reason": "rate_limited" if last_failure_was_rate_limit else "other"}

    result = _finalize_result(parsed)
    result["model_used"] = model
    return result


# --- Batch estimation ------------------------------------------------
#
# The single highest-impact quota optimization available: Gemini's RPM
# limit counts REQUESTS, not images-per-request. A single request can
# contain multiple images. So when several photos are ALREADY queued at
# once (real concurrent load - the exact scenario the free tier struggles
# with), analyzing them in ONE request instead of N directly and
# proportionally reduces request count, which is the actual bottleneck.
#
# This does NOT engage for the common case of one photo at a time (see
# gemini_queue.py - batching is opportunistic, never adds artificial
# wait time hoping more photos arrive). It also intentionally caps batch
# size low (see gemini_queue.BATCH_SIZE) - a batched request's fate is
# shared across all images in it, so an unbounded batch size would mean
# one bad request fails many users at once instead of one.

BATCH_MAX_OUTPUT_TOKENS_PER_IMAGE = 1800  # extra headroom per image beyond the base budget


def _build_batch_system_prompt(corrections: list[dict], batch_size: int) -> str:
    base_prompt = _build_system_prompt(corrections)
    return base_prompt + f"""

BATCH MODE: you will be shown {batch_size} SEPARATE, UNRELATED meal photos in \
this one request, labeled "Image 1", "Image 2", etc. Analyze EACH one \
completely independently - they are different meals from possibly \
different people, never combine or cross-reference foods between them.

Respond ONLY with a JSON object of this exact shape, no other text:
{{
  "results": [
    <result for Image 1, using the exact single-image JSON shape described above>,
    <result for Image 2, same shape>,
    ...
  ]
}}
"results" must contain exactly {batch_size} objects, in the same order as \
the images were shown."""


def _call_gemini_batch(
    images: list[tuple[bytes, str]], strict: bool, corrections: list[dict], model: str = MODEL_NAME
) -> str:
    contents = []
    for i, (image_bytes, media_type) in enumerate(images, start=1):
        contents.append(f"Image {i}:")
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=media_type))

    prompt_text = "Analyze every food in each of these meal photos independently."
    if strict:
        prompt_text += (
            " Your previous response was not valid JSON. Respond with "
            "ONLY the JSON object described in your instructions - no "
            "markdown fences, no commentary, nothing before or after it."
        )
    contents.append(prompt_text)

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_build_batch_system_prompt(corrections, len(images)),
            response_mime_type="application/json",
            max_output_tokens=MAX_OUTPUT_TOKENS + BATCH_MAX_OUTPUT_TOKENS_PER_IMAGE * len(images),
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
        ),
    )
    return response.text or ""


def estimate_calories_batch(
    images: list[tuple[bytes, str]], corrections: list[dict] | None = None, model: str = MODEL_NAME
) -> dict:
    """
    images: list of (image_bytes, media_type) tuples, all already optimized.
    All images in a batch share ONE model - callers (gemini_queue) must
    only combine jobs that were assigned the same model for A/B testing.

    Returns a dict with a "status" key:
      - "ok": "results" is a list of finalized per-image results, same
        length and order as `images`, each shaped exactly like a single
        estimate_calories() return value.
      - "failed": the WHOLE batch failed (see "reason", same semantics as
        estimate_calories) - caller must apply this outcome to every job
        in the batch, since it was one shared request.
    """
    corrections = corrections or []
    parsed = None
    last_failure_was_rate_limit = False

    for attempt in range(1, MAX_ATTEMPTS + 1):
        strict = attempt > 1
        try:
            raw_text = _call_gemini_batch(images, strict, corrections, model=model)
        except Exception as exc:
            is_retryable, suggested_wait = _classify_and_log(exc, attempt)
            last_failure_was_rate_limit = isinstance(exc, genai_errors.APIError) and exc.code == 429

            if not is_retryable or attempt == MAX_ATTEMPTS:
                break

            computed_backoff = min(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)
            wait = min(suggested_wait, MAX_BACKOFF_SECONDS) if suggested_wait else computed_backoff
            time.sleep(wait)
            continue

        parsed = _extract_json(raw_text)
        if parsed is not None and isinstance(parsed.get("results"), list) and len(parsed["results"]) == len(images):
            break
        logger.warning(
            "[JSON_PARSE] Batch response invalid or wrong length on attempt %d: %.200s",
            attempt, raw_text,
        )
        parsed = None
        if attempt < MAX_ATTEMPTS:
            time.sleep(1)

    if parsed is None:
        return {"status": "failed", "reason": "rate_limited" if last_failure_was_rate_limit else "other"}

    finalized = [_finalize_result(r) for r in parsed["results"]]
    for r in finalized:
        r["model_used"] = model
    return {"status": "ok", "results": finalized}


def _finalize_result(result: dict) -> dict:
    """Fills in safe fallbacks, applies fuzzy glossary matching as a
    safety net, and recomputes totals from the items so the numbers stay
    internally consistent even if the model's own math drifts."""

    if result.get("no_food_detected") and not result.get("foods"):
        return {"status": "no_food"}

    foods = result.get("foods") or []
    if not foods:
        # No explicit "no food" flag but also nothing returned - treat as
        # a technical failure, never show a fake 0-kcal "Unknown" result.
        return {"status": "failed"}

    for food in foods:
        food.setdefault("name_kurdish", "خواردنێکی نەناسراو")
        food.setdefault("emoji", "🍽️")
        food.setdefault("portion_kurdish", "نادیار")
        food.setdefault("kcal", 0)
        food.setdefault("protein_g", 0)
        food.setdefault("carbs_g", 0)
        food.setdefault("fat_g", 0)
        food.setdefault("matched_glossary", False)

        if not food["matched_glossary"]:
            match = find_glossary_match(food["name_kurdish"])
            if match:
                food["matched_glossary"] = True
                food["name_kurdish"] = match["name"]
                food["emoji"] = match["emoji"]

    result["foods"] = foods
    result.setdefault("total_kcal", sum(f["kcal"] for f in foods))
    result.setdefault("total_protein_g", sum(f["protein_g"] for f in foods))
    result.setdefault("total_carbs_g", sum(f["carbs_g"] for f in foods))
    result.setdefault("total_fat_g", sum(f["fat_g"] for f in foods))
    result.setdefault("confidence", "مامناوەند")
    result.setdefault("note_kurdish", "")
    result.setdefault("insight_kurdish", "")
    result.setdefault("alternatives", [])

    result["status"] = "ok"
    return result
