# review_feedback.py
#
# Run this anytime with: python review_feedback.py
# Prints recent 👎 "wrong" feedback so you know what to fix or add in
# kurdish_foods.py. Not part of the bot itself - just a lookup tool for you.

from storage import get_wrong_feedback_log

rows = get_wrong_feedback_log()

if not rows:
    print("No 'wrong' feedback logged yet.")
else:
    print(f"{len(rows)} flagged result(s) to review:\n")
    for r in rows:
        print(
            f"- {r['created_at']} | guessed: {r['food_name_kurdish']} "
            f"({r['food_name_english']}) | {r['kcal']} kcal | "
            f"matched_glossary={bool(r['matched_glossary'])}"
        )
    print(
        "\nFor each of these: if it's a Kurdish dish not in your glossary "
        "yet, add it to kurdish_foods.py with the correct name/kcal/macros."
    )
