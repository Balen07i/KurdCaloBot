# vision.py
#
# Sends a food photo + the Kurdish dish glossary to Gemini's vision API
# and parses back a structured, multi-food calorie + macro estimate,
# plus a short personalized Kurdish nutrition insight.
#
# Uses Google's free Gemini API tier (see README for how to get a key).

import json
import os

from google import genai
from google.genai import types

from kurdish_foods import build_glossary_prompt

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = "gemini-2.5-flash"  # fast, high-quality vision, generous free tier

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

YOUR TASK:
1. Identify every distinct food visible in the photo separately (e.g. rice, \
stew, and salad on one plate are three separate items, not one).
2. For EACH food, estimate its portion size in a natural human way (e.g. \
"کاسەیەک (~200g)", "پارچەیەک (~150g)", "٢ دانە") - not just raw grams with \
no context.
3. For EACH food, estimate calories, protein, carbs, and fat separately, \
scaled to the estimated portion.
4. Add up all items into a total.
5. Give one overall confidence level for the whole analysis: "بەرز" (high), \
"مامناوەند" (medium), or "نزم" (low) - based on image clarity, how well the \
items matched the glossary, and how easy the portions were to judge.
6. Write one short natural sentence in Kurdish explaining anything uncertain \
(camera angle, hidden portion, unclear dish, etc). If nothing is uncertain, \
briefly confirm the estimate is straightforward.
7. Write ONE short, natural, non-judgmental nutrition insight in Kurdish that \
is specific to what was actually detected - not a generic tip. Match this tone \
and length (do not copy these, write a new one for this meal):
{INSIGHT_STYLE_EXAMPLES}

LANGUAGE RULES:
- Every piece of Kurdish text you write must be natural, everyday spoken \
Sorani Kurdish as used in the Kurdistan Region - never a stiff or literal \
translation.
- Do not attach English names to food unless there is genuinely no common \
Kurdish name for it.
- Reuse the exact name and emoji from the glossary whenever a food matches it.

Respond ONLY with a JSON object, no other text, no markdown fences, in this \
exact shape:
{{
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

Macro rules: for each food, kcal ≈ protein_g*4 + carbs_g*4 + fat_g*9 (rough \
ballpark, doesn't need to match exactly). Totals must equal the sum of all \
items. Never refuse to estimate - always give your best guess even with low \
confidence, and reflect that uncertainty in the confidence field, not by \
skipping the estimate."""


def estimate_calories(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    image_bytes: raw bytes of the photo (as downloaded from Telegram)
    media_type: "image/jpeg" or "image/png"
    Returns a dict matching the JSON shape described in SYSTEM_PROMPT.
    """
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=media_type),
            "Analyze every food in this meal photo.",
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            max_output_tokens=800,
        ),
    )

    raw_text = (response.text or "").strip()

    # Defensive parsing in case the model wraps JSON in fences despite instructions
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        result = {}

    return _apply_safe_defaults(result)


def _apply_safe_defaults(result: dict) -> dict:
    """Fills in safe fallbacks so the bot never crashes on a malformed
    or empty model response, and totals always exist even if missing."""
    if not result.get("foods"):
        result["foods"] = [
            {
                "name_kurdish": "نەناسراو",
                "emoji": "❓",
                "portion_kurdish": "نادیار",
                "kcal": 0,
                "protein_g": 0,
                "carbs_g": 0,
                "fat_g": 0,
                "matched_glossary": False,
            }
        ]

    for food in result["foods"]:
        food.setdefault("name_kurdish", "نەناسراو")
        food.setdefault("emoji", "❓")
        food.setdefault("portion_kurdish", "نادیار")
        food.setdefault("kcal", 0)
        food.setdefault("protein_g", 0)
        food.setdefault("carbs_g", 0)
        food.setdefault("fat_g", 0)
        food.setdefault("matched_glossary", False)

    # Recompute totals from items if the model didn't provide them, so the
    # numbers are always internally consistent.
    result.setdefault("total_kcal", sum(f["kcal"] for f in result["foods"]))
    result.setdefault("total_protein_g", sum(f["protein_g"] for f in result["foods"]))
    result.setdefault("total_carbs_g", sum(f["carbs_g"] for f in result["foods"]))
    result.setdefault("total_fat_g", sum(f["fat_g"] for f in result["foods"]))

    result.setdefault("confidence", "نزم")
    result.setdefault(
        "note_kurdish", "نەتوانرا وێنەکە بە باشی شیکار بکرێت، تکایە دووبارە هەوڵبدەرەوە."
    )
    result.setdefault("insight_kurdish", "🍽️ خواردنێکی گشتی، هەوڵبدە هاوسەنگ بێت.")

    return result
