# kurdish_foods.py
#
# Reference glossary of common Kurdish / regional dishes with rough
# calories + macros per typical serving. Injected into every vision-API
# call so the model recognizes local dishes correctly instead of guessing,
# and reuses the same emoji + Kurdish name every time for consistency.
#
# HOW TO ADD OR FIX A DISH (no coding needed beyond copy/paste):
# Add a new entry to KURDISH_FOOD_GLOSSARY below, following the same shape.
# - "name": canonical Kurdish name shown to users (no English clutter)
# - "emoji": one emoji that best represents the dish
# - "aliases": alternate spellings / regional names / English search terms —
#              used only for matching, never shown to the user
# - "kcal", "protein_g", "carbs_g", "fat_g": per ONE typical serving/plate
#
# That's it — nothing else in the codebase needs to change when you add,
# edit, or remove a dish here.

KURDISH_FOOD_GLOSSARY = [
    {
        "name": "دۆلمە", "emoji": "🫑",
        "aliases": ["Dolma", "stuffed grape leaves", "stuffed vegetables"],
        "kcal": 320, "protein_g": 12, "carbs_g": 40, "fat_g": 12,
    },
    {
        "name": "کوبە", "emoji": "🥟",
        "aliases": ["Kubba", "Kifta", "Kubbeh", "stuffed bulgur shell"],
        "kcal": 280, "protein_g": 15, "carbs_g": 25, "fat_g": 13,
    },
    {
        "name": "برنجی بریانی", "emoji": "🍛",
        "aliases": ["Biryani", "Kurdish spiced rice"],
        "kcal": 550, "protein_g": 28, "carbs_g": 65, "fat_g": 18,
    },
    {
        "name": "قەڵیاکاوە", "emoji": "🍳",
        "aliases": ["Qellyakawa", "Kurdish breakfast egg fry"],
        "kcal": 260, "protein_g": 14, "carbs_g": 10, "fat_g": 18,
    },
    {
        "name": "تریشک", "emoji": "🍲",
        "aliases": ["Tirshik", "Tirşik", "sour herb lentil stew"],
        "kcal": 200, "protein_g": 9, "carbs_g": 28, "fat_g": 6,
    },
    {
        "name": "کەللەپاچە", "emoji": "🍲",
        "aliases": ["Kelle Pach", "head and trotter soup"],
        "kcal": 400, "protein_g": 30, "carbs_g": 8, "fat_g": 26,
    },
    {
        "name": "شۆربە", "emoji": "🥣",
        "aliases": ["Shorba", "Şorbe", "Kurdish lentil soup", "vegetable soup"],
        "kcal": 180, "protein_g": 9, "carbs_g": 26, "fat_g": 4,
    },
    {
        "name": "ڕەندی", "emoji": "🍚",
        "aliases": ["Rendayi", "Rendi", "bulgur pilaf"],
        "kcal": 300, "protein_g": 8, "carbs_g": 55, "fat_g": 6,
    },
    {
        "name": "یاپراخ", "emoji": "🫑",
        "aliases": ["Yaprax", "vegetarian grape leaf dolma"],
        "kcal": 250, "protein_g": 5, "carbs_g": 42, "fat_g": 8,
    },
    {
        "name": "کەبابی کوردی", "emoji": "🍢",
        "aliases": ["Kebab Kurdi", "grilled minced meat skewer"],
        "kcal": 450, "protein_g": 32, "carbs_g": 5, "fat_g": 33,
    },
    {
        "name": "تەپسی کەباب", "emoji": "🍖",
        "aliases": ["Tepsi Kebab", "oven-baked meat and vegetable tray"],
        "kcal": 500, "protein_g": 30, "carbs_g": 20, "fat_g": 32,
    },
    {
        "name": "نان", "emoji": "🫓",
        "aliases": ["Naan-e Kurdi", "Kurdish flatbread"],
        "kcal": 150, "protein_g": 5, "carbs_g": 30, "fat_g": 1,
    },
    {
        "name": "خۆرشینی", "emoji": "🍚",
        "aliases": ["Xwarshini", "rice with raisins chickpeas and meat"],
        "kcal": 480, "protein_g": 20, "carbs_g": 60, "fat_g": 16,
    },
    {
        "name": "شلێر", "emoji": "🍳",
        "aliases": ["Shler", "Kurdish egg and vegetable breakfast"],
        "kcal": 300, "protein_g": 14, "carbs_g": 15, "fat_g": 20,
    },
    {
        "name": "پاقلای بێ گۆشت", "emoji": "🫘",
        "aliases": ["Paqla be gosht", "fava bean stew no meat"],
        "kcal": 220, "protein_g": 10, "carbs_g": 32, "fat_g": 6,
    },
    {
        "name": "پاقلای بە گۆشت", "emoji": "🫘",
        "aliases": ["Paqla be gosht meat", "fava bean stew with meat"],
        "kcal": 350, "protein_g": 20, "carbs_g": 32, "fat_g": 15,
    },
    {
        "name": "مومبار", "emoji": "🌭",
        "aliases": ["Mumbar", "stuffed intestine with rice"],
        "kcal": 380, "protein_g": 16, "carbs_g": 30, "fat_g": 22,
    },
    {
        "name": "برنج", "emoji": "🍚",
        "aliases": ["plain buttered rice", "birinc"],
        "kcal": 250, "protein_g": 5, "carbs_g": 48, "fat_g": 5,
    },
    {
        "name": "ماست و خیار", "emoji": "🥒",
        "aliases": ["Mast u xiyar", "yogurt and cucumber"],
        "kcal": 90, "protein_g": 5, "carbs_g": 8, "fat_g": 4,
    },
    {
        "name": "تورشی", "emoji": "🥒",
        "aliases": ["Turshi", "Kurdish pickled vegetables"],
        "kcal": 40, "protein_g": 1, "carbs_g": 8, "fat_g": 0,
    },
    {
        "name": "بەقلاوە", "emoji": "🍯",
        "aliases": ["Baqlawa", "Baklava"],
        "kcal": 330, "protein_g": 5, "carbs_g": 38, "fat_g": 18,
    },
    {
        "name": "حەلوا", "emoji": "🍯",
        "aliases": ["Helwa", "Halva"],
        "kcal": 300, "protein_g": 6, "carbs_g": 30, "fat_g": 18,
    },
    {
        "name": "چای", "emoji": "🍵",
        "aliases": ["Chay be shekir", "Kurdish sweet tea"],
        "kcal": 40, "protein_g": 0, "carbs_g": 10, "fat_g": 0,
    },
    {
        "name": "کوتڵک", "emoji": "🥟",
        "aliases": ["Kutilk", "dumplings in yogurt garlic sauce"],
        "kcal": 400, "protein_g": 15, "carbs_g": 45, "fat_g": 17,
    },
    {
        "name": "پەردە پیلاو", "emoji": "🍚",
        "aliases": ["Perde Pilav", "rice wrapped in dough"],
        "kcal": 500, "protein_g": 20, "carbs_g": 60, "fat_g": 18,
    },
    {
        "name": "ساوار", "emoji": "🥣",
        "aliases": ["Sawar", "bulgur soup"],
        "kcal": 180, "protein_g": 7, "carbs_g": 30, "fat_g": 4,
    },
    {
        "name": "مریشکی برژاو", "emoji": "🍗",
        "aliases": ["Kurdish grilled chicken", "Mereq chicken"],
        "kcal": 400, "protein_g": 38, "carbs_g": 2, "fat_g": 26,
    },
    {
        "name": "مەرەق", "emoji": "🍲",
        "aliases": ["Mereq", "Kurdish meat and vegetable stew"],
        "kcal": 380, "protein_g": 25, "carbs_g": 20, "fat_g": 20,
    },
    {
        "name": "فرنی", "emoji": "🍮",
        "aliases": ["Firni", "Muhallabia", "Kurdish milk pudding"],
        "kcal": 220, "protein_g": 5, "carbs_g": 35, "fat_g": 6,
    },
    {
        "name": "نانی پەنیر و سەوزە", "emoji": "🧀",
        "aliases": ["Geyre", "flatbread with cheese and herbs"],
        "kcal": 260, "protein_g": 10, "carbs_g": 30, "fat_g": 10,
    },
    {
        "name": "نۆکی خواردن", "emoji": "🫘",
        "aliases": ["chickpea based dish", "Xwarina naskek"],
        "kcal": 300, "protein_g": 12, "carbs_g": 45, "fat_g": 8,
    },
]


def build_glossary_prompt() -> str:
    """
    Returns a formatted string block to inject into the vision model's
    prompt so it recognizes local dishes by name, alias, or region — and
    reuses the same Kurdish name + emoji every time for consistency.
    """
    lines = []
    for dish in KURDISH_FOOD_GLOSSARY:
        alias_str = ", ".join(dish["aliases"])
        lines.append(
            f"- {dish['emoji']} {dish['name']} (matches: {alias_str}): "
            f"~{dish['kcal']} kcal, {dish['protein_g']}g protein, "
            f"{dish['carbs_g']}g carbs, {dish['fat_g']}g fat per typical serving"
        )
    return (
        "Reference list of common Kurdish/regional dishes with their exact "
        "Kurdish name, emoji, and typical calories/macros per one serving. "
        "If a food in the photo closely matches one of these (by name, "
        "alias, or visual similarity), use this exact name and emoji, and "
        "use these numbers as your primary estimate, adjusted for the "
        "visible portion size. If a food does not match any of these, "
        "give your own best-guess Kurdish name, a fitting emoji, and mark "
        "it clearly as not matched.\n\n" + "\n".join(lines)
    )
