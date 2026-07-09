# vision.py
#
# Sends a food photo + the Kurdish dish glossary to Gemini's vision API
# and parses back a structured calorie + macro estimate.
#
# Uses Google's free Gemini API tier (see README for how to get a key).

import json
import os

from google import genai
from google.genai import types

from kurdish_foods import build_glossary_prompt

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = "gemini-2.5-flash"  # fast, high-quality vision, generous free tier

SYSTEM_PROMPT = f"""You are a nutrition estimation assistant for a Kurdish-language \
calorie and macro tracking bot. You will be shown a photo of a meal or food item.

{build_glossary_prompt()}

Respond ONLY with a JSON object, no other text, no markdown fences, in this \
exact shape:
{{
  "food_name_kurdish": "name of the food in Kurdish (Sorani script)",
  "food_name_english": "short English name",
  "estimated_kcal": integer,
  "protein_g": integer,
  "carbs_g": integer,
  "fat_g": integer,
  "confidence": "high" | "medium" | "low",
  "matched_glossary": true or false,
  "note_kurdish": "one short natural sentence in Kurdish about portion size or uncertainty"
}}

Macro rules:
- protein_g, carbs_g, fat_g should be your best estimate in grams for the
  whole visible portion, consistent with estimated_kcal (roughly:
  kcal ≈ protein_g*4 + carbs_g*4 + fat_g*9 — they don't need to match
  exactly, but should be in the right ballpark).

Confidence should be "low" whenever the dish is not a clear match to the \
glossary or the portion size is hard to judge from the photo. Never refuse \
to estimate - always give your best guess even with low confidence."""


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
            "Estimate the calories and macros in this meal photo.",
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            max_output_tokens=400,
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

    # Fill in safe defaults for any missing field so the bot never crashes
    # on a malformed model response.
    defaults = {
        "food_name_kurdish": "نەناسراو",
        "food_name_english": "Unknown",
        "estimated_kcal": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fat_g": 0,
        "confidence": "low",
        "matched_glossary": False,
        "note_kurdish": "نەتوانرا وێنەکە بە باشی شیکار بکرێت، تکایە دووبارە هەوڵبدەرەوە.",
    }
    for key, default_value in defaults.items():
        result.setdefault(key, default_value)

    return result
