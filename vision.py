# vision.py
#
# Sends a food photo + the Kurdish dish glossary (+ any learned user
# corrections) to Gemini's vision API and parses back a structured,
# multi-food calorie + macro estimate, plus a short personalized Kurdish
# nutrition insight.
#
# Uses Google's free Gemini API tier - no paid service anywhere in here.

import json
import logging
import os
import re

from google import genai
from google.genai import types

from kurdish_foods import build_confusable_prompt, build_glossary_prompt, find_glossary_match

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = "gemini-2.5-flash"  # fast, high-quality vision, generous free tier

# IMPORTANT: gemini-2.5-flash spends part of max_output_tokens on internal
# "thinking" before it writes the final answer. Too small a budget was the
# root cause of a real bug where JSON got truncated mid-way and silently
# fell back to a fake "Unknown / 0 kcal" result. thinking_budget caps how
# much of the budget thinking can eat; max_output_tokens leaves generous
# room for the JSON itself on top of that.
THINKING_BUDGET = 1200
MAX_OUTPUT_TOKENS = 3500

INSIGHT_STYLE_EXAMPLES = """\
- 💪 ئەم خواردنە سەرچاوەیەکی باشی پرۆتینە.
- 🥗 زیادکردنی سەوزە فایبەری خواردنەکەت زیاد دەکات.
- 🔥 بۆ کێش زیادکردن زۆر گونجاوە.
- ⚖️ ئەگەر ئامانجت کەمکردنەوەی کێشە، واباشە قەبارەی برنج کەمتر بێت.
- 💧 بیرت نەچێت لەگەڵ ئەم خواردنە ئاوی تەواو بخۆیت."""


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
2. Portion: for EACH food, estimate its portion using whichever unit fits \
best (grams, pieces/دانە, cups/کاسە, slices/پارچە). Use visible reference \
objects to judge scale - a standard dinner plate is ~25-28cm across, a \
tablespoon holds ~15ml, a person's palm is roughly one portion of meat, a \
teacup is ~200ml. Compare the food to whatever reference objects (plate, \
bowl, spoon, fork, hand, cup) are actually visible in the photo. For food \
that's mixed, stacked, or spread across the plate, estimate volume by \
visualizing it separated out, not just by its 2D footprint in the photo.
3. Nutrition: for EACH food, calculate calories, protein, carbs, and fat \
scaled to that estimated portion, and factor in the visible cooking method \
(grilled/fried/boiled/raw change fat content significantly) and any oils, \
butter, ghee, or sauces you can ACTUALLY see evidence of - never add these \
by default "just in case".
4. Only after steps 1-3 are done for every item, produce the final JSON.

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


def _call_gemini(image_bytes: bytes, media_type: str, strict: bool, corrections: list[dict]) -> str:
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


def estimate_calories(
    image_bytes: bytes, media_type: str = "image/jpeg", corrections: list[dict] | None = None
) -> dict:
    """
    Returns a dict with a "status" key:
      - "ok": normal result (see _finalize_result for full shape, includes
        an "alternatives" list which is usually empty)
      - "no_food": Gemini determined the photo genuinely has no food
      - "failed": technical failure - caller should show photo-quality tips
    """
    corrections = corrections or []
    parsed = None

    for attempt, strict in enumerate((False, True)):
        try:
            raw_text = _call_gemini(image_bytes, media_type, strict, corrections)
        except Exception:
            logger.exception("Gemini API call failed (attempt %d)", attempt + 1)
            continue

        parsed = _extract_json(raw_text)
        if parsed is not None:
            break
        logger.warning(
            "Could not parse Gemini response as JSON (attempt %d): %.200s",
            attempt + 1, raw_text,
        )

    if parsed is None:
        return {"status": "failed"}

    return _finalize_result(parsed)


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
