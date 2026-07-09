# review_feedback.py
#
# Run this anytime with: python review_feedback.py
# Prints recent 👎 "wrong" feedback so you know what to fix or add in
# kurdish_foods.py. Not part of the bot itself - just a lookup tool for you.

import json

from storage import get_wrong_feedback_log

rows = get_wrong_feedback_log()

if not rows:
    print("No 'wrong' feedback logged yet.")
else:
    print(f"{len(rows)} flagged result(s) to review:\n")
    for r in rows:
        foods = json.loads(r["foods_json"] or "[]")
        food_list = ", ".join(
            f"{f['emoji']} {f['name_kurdish']} ({f['portion_kurdish']}, "
            f"{f['kcal']} kcal, matched={f['matched_glossary']})"
            for f in foods
        )
        print(f"- {r['created_at']}")
        print(f"  foods: {food_list or r['food_name_kurdish']}")
        print(f"  total: {r['kcal']} kcal | confidence: {r['confidence']}")
        print()
    print(
        "For each of these: if it's a Kurdish dish not in your glossary yet, "
        "or matched incorrectly, add/fix it in kurdish_foods.py with the "
        "correct name/emoji/kcal/macros."
    )
