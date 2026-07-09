# vision.py
#
# Sends a food photo + the Kurdish dish glossary to Gemini's vision API
# and parses back a structured, multi-food calorie + macro estimate,
# plus a short personalized Kurdish nutrition insight.
#
# Uses Google's free Gemini API tier (see README for how to get a key).

import json
import logging
import os
import re

from google import genai
from google.genai import types

from kurdish_foods import build_glossary_prompt, find_glossary_match

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = "gemini-2.5-flash"  # fast, high-quality vision, generous free tier

# IMPORTANT: gemini-2.5-flash spends part of max_output_tokens on internal
# "thinking" before it writes the final answer. A budget that's too small
# was the root cause of a real bug: the JSON got truncated mid-way,
# json.loads() failed, and the bot silently fell back to "Unknown / 0
# kcal" even for a perfectly clear photo. thinking_budget below caps how
# much of the budget thinking can eat, and max_output_tokens leaves
# generous headroom for the actual JSON on top of that.
THINKING_BUDGET = 1024
MAX_OUTPUT_TOKENS = 3000

# A handful of real example insights (in the exact tone we want) purely to
# calibrate style. Gemini must never copy these verbatim - it should write
# ONE new sentence that actually matches the detected meal.
INSIGHT_STYLE_EXAMPLES = """\
- 💪 ئەم خواردنە سەرچاوەیەکی باشی پرۆتینە.
- 🥗 زیادکردنی سەوزە فایبەری خواردنەکەت زیاد دەکات.
- 🔥 بۆ کێش زیادکردن زۆر گونجاوە.
- ⚖️ ئەگەر ئامانجت کەمکردنەوەی کێشە، واباشە قەبارەی برنج کەمتر بێت.
- 💧 بیرت نەچێت لەگەڵ ئەم خواردنە ئاوی تەواو بخۆیت."""

SYSTEM_PROMPT = f"""You are a friendly nutrition-tracking assistant for a Kurdish \
(Sorani) audience in the Kurdistan Region. You will be shown a photo of a meal \
that may contain one or several different foods on the same plate or table.

{build_glossary_prompt()}

REASON IN THIS ORDER (internally - only the final JSON is shown to the user):
1. Identify: scan the whole image and list every distinct FOOD item. Ignore \
plates, bowls, cups, cutlery, napkins, hands, tables, and background objects \
- those are not foods. If two foods are touching or slightly overlapping \
(e.g. rice next to stew, sauce over meat), still list them as separate items \
- do not merge different foods into one entry, and do not split one food into \
duplicate entries either.
2. Portion: for EACH food, judge its portion using whichever unit fits it \
best - grams for scoopable/loose food, pieces/دانە for countable items, \
cups/کاسە for rice or soup, slices/پارچە for bread or meat cuts. Always give \
a natural human description, not just a raw number (e.g. "کاسەیەک (~200g)", \
"٢ پارچە", "٣ دانە").
3. Nutrition: for EACH food, calculate calories, protein, carbs, and fat \
scaled to that estimated portion.
4. Only after steps 1-3 are done for every item, produce the final JSON \
totals and confidence assessment described below.

RECOGNIZING COMMON STAPLES - be decisive, not cautious:
Rice, bread/naan, grilled or stewed meat, chicken, fish, eggs, milk/yogurt, \
fruit, and vegetables are all everyday foods that are usually easy to \
recognize even in an imperfect photo. If any of these (or anything else \
reasonably identifiable) is visible, you MUST attempt a real estimate for \
it. Only use "no food detected" when the photo genuinely shows no food at \
all (e.g. an empty table, a person, an unrelated object) - never as a way \
to avoid estimating something you can actually see.

HANDLING DIFFICULT PHOTOS:
Low light, partial plates, close-up crops, mild blur, or mixed/overlapping \
meals should NOT stop you from estimating - they should lower your \
confidence instead, with a short honest note about what made it harder. \
A best-effort estimate is always more useful to the user than refusing.

CONFIDENCE RULES:
Base confidence ONLY on: image clarity/lighting, how clearly each food is \
visible (not cut off, not obscured), how certain the identification is, and \
how visible the portion/quantity is. The NUMBER OF FOOD ITEMS on the plate \
is never by itself a reason to lower confidence - a clear photo of five \
distinct foods can still be "بەرز" (high) if each one is clearly visible.

FOOD MATCHING:
Match foods to the glossary above by meaning, not exact wording - e.g. \
"grilled chicken" or slightly different spellings/synonyms should still \
match a glossary chicken entry if it's clearly the same dish. When matched, \
reuse the glossary's exact Kurdish name and emoji.

LANGUAGE RULES:
- Every piece of Kurdish text you write must be natural, everyday spoken \
Sorani Kurdish as used in the Kurdistan Region - never a stiff or literal \
translation.
- Do not attach English names to food unless there is genuinely no common \
Kurdish name for it.

Write ONE short, natural, non-judgmental nutrition insight in Kurdish that \
is specific to what was actually detected - not a generic tip. Match this \
tone and length (do not copy these, write a new one for this meal):
{INSIGHT_STYLE_EXAMPLES}

Respond ONLY with a JSON object, no other text, no markdown fences, in this \
exact shape:
{{
  "no_food_detected": true or false,
  "foods": [
    {{
      "name_kurdish": "...",
      "emoji": "🍚",
      "portion_kurdish": "...",
      "kcal": integer,
      "protein_g": integer,
      "carbs_g": integer,
      "fat_g": integer,
      "matched_glossary": true or false
    }}
  ],
  "total_kcal": integer,
  "total_protein_g": integer,
  "total_carbs_g": integer,
  "total_fat_g": integer,
  "confidence": "بەرز" | "مامناوەند" | "نزم",
  "note_kurdish": "one short sentence",
  "insight_kurdish": "one short sentence, starting with a fitting emoji"
}}

If no_food_detected is true, "foods" must be an empty list and the other \
numeric fields must be 0 - use this ONLY when there is genuinely no food in \
the photo, per the staples rule above.

Macro rules: for each food, kcal ≈ protein_g*4 + carbs_g*4 + fat_g*9 (rough \
ballpark, doesn't need to match exactly). Totals must equal the sum of all \
items."""


def _call_gemini(image_bytes: bytes, media_type: str, strict: bool) -> str:
    prompt_text = "Analyze every food in this meal photo."
    if strict:
        prompt_text += (
            " Your previous response was not valid JSON. Respond with "
            "ONLY the JSON object described in your instructions - no "
            "markdown fences, no commentary, nothing before or after it."
        )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=media_type),
            prompt_text,
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
        ),
    )
    return response.text or ""


def _extract_json(raw_text: str):
    """
    Tolerant JSON extraction: handles a clean JSON response (the normal
    case), a response wrapped in markdown fences, and a response with
    stray text before/after the JSON object - instead of failing outright
    on any minor formatting deviation.
    """
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

    # Last resort: pull out the largest {...} block and try that alone -
    # catches cases where the model added a stray sentence before/after.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def estimate_calories(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    image_bytes: raw bytes of the photo (as downloaded from Telegram)
    media_type: "image/jpeg" or "image/png"

    Returns a dict with a "status" key:
      - "ok": normal result, see _finalize_result() for the full shape
      - "no_food": Gemini determined the photo genuinely has no food in it
      - "failed": technical failure (API error or unparseable response
        after retrying) - the caller should show photo-quality tips
    """
    parsed = None

    for attempt, strict in enumerate((False, True)):
        try:
            raw_text = _call_gemini(image_bytes, media_type, strict=strict)
        except Exception:
            logger.exception("Gemini API call failed (attempt %d)", attempt + 1)
            continue

        parsed = _extract_json(raw_text)
        if parsed is not None:
            break
        logger.warning(
            "Could not parse Gemini response as JSON (attempt %d): %.200s",
            attempt + 1,
            raw_text,
        )

    if parsed is None:
        return {"status": "failed"}

    return _finalize_result(parsed)


def _finalize_result(result: dict) -> dict:
    """Fills in safe fallbacks, applies fuzzy glossary matching as a
    safety net, and recomputes totals from the items so the numbers are
    always internally consistent - even if the model's own math is off."""

    if result.get("no_food_detected") and not result.get("foods"):
        return {"status": "no_food"}

    foods = result.get("foods") or []
    if not foods:
        # Model didn't explicitly say "no food" but also gave nothing -
        # treat as a technical failure rather than showing a fake 0-kcal
        # "Unknown" result to the user.
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

        # Fuzzy-match safety net: if the model didn't already mark this as
        # a glossary match, double check ourselves - catches synonyms and
        # spelling variations the model's own judgment missed, and
        # relabels with our canonical name/emoji for consistency.
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

    result["status"] = "ok"
    return result
