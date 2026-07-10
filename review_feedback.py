# review_feedback.py
#
# Run this anytime with: python review_feedback.py
# Prints recent 👎 "wrong" feedback (what to fix in kurdish_foods.py) and
# recent user-submitted corrections (the free "learning" loop - these are
# already being reused automatically in every future prompt, this is just
# for your own visibility into what's been learned).

import json

from storage import get_all_corrections, get_wrong_feedback_log

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
        "correct name/emoji/kcal/macros.\n"
    )

print("=" * 50)
corrections = get_all_corrections()
if not corrections:
    print("No user corrections submitted yet.")
else:
    print(f"{len(corrections)} learned correction(s) (already active in every prompt):\n")
    for c in corrections:
        print(f'  "{c["wrong_name"]}" -> {c["correct_name_kurdish"]}')
    print(
        "\nIf any of these show up often, consider adding them as a proper "
        "glossary entry in kurdish_foods.py instead - it's more reliable "
        "than relying on the correction list forever."
    )
