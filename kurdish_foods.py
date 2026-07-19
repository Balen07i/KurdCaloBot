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

    # --- Drinks ------------------------------------------------------
    {
        "name": "دۆو", "emoji": "🥛",
        "aliases": ["Dogh", "Ayran", "yogurt drink", "salted yogurt drink"],
        "kcal": 60, "protein_g": 3, "carbs_g": 5, "fat_g": 2,
    },
    {
        "name": "شەربەت", "emoji": "🧃",
        "aliases": ["Sherbet", "Kurdish fruit syrup drink"],
        "kcal": 120, "protein_g": 0, "carbs_g": 30, "fat_g": 0,
    },
    {
        "name": "قاوەی کوردی", "emoji": "☕",
        "aliases": ["Kurdish coffee", "qawa"],
        "kcal": 5, "protein_g": 0, "carbs_g": 1, "fat_g": 0,
    },
    {
        "name": "شیری گەرم", "emoji": "🥛",
        "aliases": ["warm milk", "milk"],
        "kcal": 150, "protein_g": 8, "carbs_g": 12, "fat_g": 8,
    },
    {
        "name": "ئاوی هەنار", "emoji": "🍹",
        "aliases": ["pomegranate juice"],
        "kcal": 130, "protein_g": 1, "carbs_g": 32, "fat_g": 0,
    },
    {
        "name": "شەربەتی لیمۆ", "emoji": "🍋",
        "aliases": ["lemonade", "lemon drink"],
        "kcal": 100, "protein_g": 0, "carbs_g": 26, "fat_g": 0,
    },

    # --- Desserts ------------------------------------------------------
    {
        "name": "کنافە", "emoji": "🍮",
        "aliases": ["Knafeh", "Kunafa"],
        "kcal": 400, "protein_g": 8, "carbs_g": 50, "fat_g": 20,
    },
    {
        "name": "زەردە", "emoji": "🍮",
        "aliases": ["Zerde", "saffron rice pudding"],
        "kcal": 250, "protein_g": 3, "carbs_g": 50, "fat_g": 5,
    },
    {
        "name": "شامی", "emoji": "🍪",
        "aliases": ["Shami sweet", "Kurdish semolina cookie"],
        "kcal": 180, "protein_g": 3, "carbs_g": 24, "fat_g": 9,
    },
    {
        "name": "بەستەنی", "emoji": "🍦",
        "aliases": ["Bastani", "Kurdish ice cream"],
        "kcal": 220, "protein_g": 4, "carbs_g": 28, "fat_g": 10,
    },

    # --- Fruits ------------------------------------------------------
    {
        "name": "هەنار", "emoji": "🍒",
        "aliases": ["pomegranate", "whole pomegranate or seeds"],
        "kcal": 105, "protein_g": 1, "carbs_g": 26, "fat_g": 1,
    },
    {
        "name": "سێو", "emoji": "🍎",
        "aliases": ["apple"],
        "kcal": 95, "protein_g": 0, "carbs_g": 25, "fat_g": 0,
    },
    {
        "name": "پرتەقاڵ", "emoji": "🍊",
        "aliases": ["orange"],
        "kcal": 65, "protein_g": 1, "carbs_g": 16, "fat_g": 0,
    },
    {
        "name": "قەوون", "emoji": "🍈",
        "aliases": ["melon"],
        "kcal": 60, "protein_g": 1, "carbs_g": 15, "fat_g": 0,
    },
    {
        "name": "زبەش", "emoji": "🍉",
        "aliases": ["watermelon"],
        "kcal": 85, "protein_g": 2, "carbs_g": 21, "fat_g": 0,
    },
    {
        "name": "ترێ", "emoji": "🍇",
        "aliases": ["grapes"],
        "kcal": 100, "protein_g": 1, "carbs_g": 27, "fat_g": 0,
    },
    {
        "name": "قەیسی", "emoji": "🍑",
        "aliases": ["apricot"],
        "kcal": 50, "protein_g": 1, "carbs_g": 12, "fat_g": 0,
    },
    {
        "name": "موز", "emoji": "🍌",
        "aliases": ["banana"],
        "kcal": 105, "protein_g": 1, "carbs_g": 27, "fat_g": 0,
    },

    # --- Vegetables ----------------------------------------------------
    {
        "name": "خیار و تەماتە", "emoji": "🥗",
        "aliases": ["cucumber tomato salad", "shirazi salad"],
        "kcal": 60, "protein_g": 2, "carbs_g": 10, "fat_g": 2,
    },
    {
        "name": "پیاز", "emoji": "🧅",
        "aliases": ["onion", "raw or cooked onion"],
        "kcal": 45, "protein_g": 1, "carbs_g": 10, "fat_g": 0,
    },
    {
        "name": "بادەمجان برژاو", "emoji": "🍆",
        "aliases": ["grilled eggplant", "roasted eggplant"],
        "kcal": 100, "protein_g": 2, "carbs_g": 15, "fat_g": 5,
    },
    {
        "name": "بامیە", "emoji": "🥘",
        "aliases": ["okra stew", "bamya"],
        "kcal": 180, "protein_g": 8, "carbs_g": 20, "fat_g": 8,
    },
    {
        "name": "فاسۆلیا", "emoji": "🫘",
        "aliases": ["green bean stew", "fasolia"],
        "kcal": 200, "protein_g": 10, "carbs_g": 22, "fat_g": 8,
    },

    # --- Sauces, oils & condiments --------------------------------------
    # NOTE: سرکەی هەنار (pomegranate molasses) and سۆسی تەماتە (tomato/red
    # sauce) are visually similar (both dark reddish, glossy, poured over
    # food) but nutritionally different - see CONFUSABLE_PAIRS below,
    # which teaches the model to actively distinguish them.
    {
        "name": "سرکەی هەنار", "emoji": "🍯",
        "aliases": ["pomegranate molasses", "narsharab", "sour pomegranate sauce"],
        "kcal": 45, "protein_g": 0, "carbs_g": 11, "fat_g": 0,
    },
    {
        "name": "سۆسی تەماتە", "emoji": "🍅",
        "aliases": ["tomato sauce", "red sauce", "sosi sur"],
        "kcal": 30, "protein_g": 1, "carbs_g": 6, "fat_g": 0,
    },
    {
        "name": "دۆنی زەیتوون", "emoji": "🫒",
        "aliases": ["olive oil", "cooking oil drizzle"],
        "kcal": 120, "protein_g": 0, "carbs_g": 0, "fat_g": 14,
    },
    {
        "name": "کەرێ", "emoji": "🧈",
        "aliases": ["butter", "ghee", "run"],
        "kcal": 100, "protein_g": 0, "carbs_g": 0, "fat_g": 11,
    },
    {
        "name": "تەهینە", "emoji": "🥣",
        "aliases": ["tahini", "sesame paste"],
        "kcal": 90, "protein_g": 3, "carbs_g": 3, "fat_g": 8,
    },

    # --- Bread & staples -------------------------------------------------
    {
        "name": "سامون", "emoji": "🥖",
        "aliases": ["samoon", "Iraqi Kurdish bread roll"],
        "kcal": 180, "protein_g": 6, "carbs_g": 34, "fat_g": 2,
    },
    {
        "name": "برنجی جوانی", "emoji": "🍚",
        "aliases": ["long grain rice", "basmati rice"],
        "kcal": 260, "protein_g": 5, "carbs_g": 50, "fat_g": 5,
    },

    # --- Meats ---------------------------------------------------------
    {
        "name": "گۆشتی بەرخ برژاو", "emoji": "🍖",
        "aliases": ["grilled lamb", "roasted lamb"],
        "kcal": 430, "protein_g": 34, "carbs_g": 0, "fat_g": 32,
    },
    {
        "name": "ماسی برژاو", "emoji": "🐟",
        "aliases": ["grilled fish", "masgouf"],
        "kcal": 300, "protein_g": 35, "carbs_g": 0, "fat_g": 17,
    },
    {
        "name": "هێلکە", "emoji": "🥚",
        "aliases": ["egg", "fried or boiled egg"],
        "kcal": 90, "protein_g": 6, "carbs_g": 1, "fat_g": 7,
    },

    # --- Herbs & aromatics -----------------------------------------------
    {
        "name": "پونگ", "emoji": "🌿",
        "aliases": ["mint", "pouneh", "wild mint"],
        "kcal": 5, "protein_g": 0, "carbs_g": 1, "fat_g": 0,
    },
    {
        "name": "جەعدە", "emoji": "🌿",
        "aliases": ["basil", "rihan"],
        "kcal": 5, "protein_g": 0, "carbs_g": 1, "fat_g": 0,
    },
    {
        "name": "توتراوی سەوز", "emoji": "🌿",
        "aliases": ["fresh herb plate", "sabzi khordan", "mixed herbs side"],
        "kcal": 25, "protein_g": 1, "carbs_g": 4, "fat_g": 0,
    },
    {
        "name": "جۆزە", "emoji": "🧄",
        "aliases": ["garlic"],
        "kcal": 15, "protein_g": 1, "carbs_g": 3, "fat_g": 0,
    },

    # --- More dairy ------------------------------------------------------
    {
        "name": "پەنیری کوردی", "emoji": "🧀",
        "aliases": ["Kurdish white cheese", "panire kurdi"],
        "kcal": 280, "protein_g": 18, "carbs_g": 3, "fat_g": 22,
    },
    {
        "name": "کەشک", "emoji": "🥣",
        "aliases": ["Kashk", "dried whey", "kashk sauce"],
        "kcal": 110, "protein_g": 9, "carbs_g": 8, "fat_g": 4,
    },
    {
        "name": "قەیماغ", "emoji": "🧈",
        "aliases": ["Kaymak", "clotted cream"],
        "kcal": 340, "protein_g": 3, "carbs_g": 2, "fat_g": 36,
    },
    {
        "name": "دۆشاو", "emoji": "🍯",
        "aliases": ["grape molasses", "doshab"],
        "kcal": 50, "protein_g": 0, "carbs_g": 13, "fat_g": 0,
    },

    # --- More bread --------------------------------------------------
    {
        "name": "نانی تەنوور", "emoji": "🫓",
        "aliases": ["tandoor bread", "taftan", "clay-oven flatbread"],
        "kcal": 200, "protein_g": 6, "carbs_g": 38, "fat_g": 2,
    },
    {
        "name": "نانی ڕۆن", "emoji": "🫓",
        "aliases": ["oil flatbread", "nan roghan"],
        "kcal": 230, "protein_g": 5, "carbs_g": 35, "fat_g": 8,
    },
    {
        "name": "سیمیت", "emoji": "🥯",
        "aliases": ["Simit", "sesame bread ring"],
        "kcal": 280, "protein_g": 8, "carbs_g": 48, "fat_g": 6,
    },

    # --- Street food & snacks ----------------------------------------
    {
        "name": "دۆنەر", "emoji": "🌯",
        "aliases": ["Doner", "shawarma", "durum"],
        "kcal": 480, "protein_g": 28, "carbs_g": 45, "fat_g": 22,
    },
    {
        "name": "لەحماجوون", "emoji": "🍕",
        "aliases": ["Lahmacun", "Turkish flatbread pizza"],
        "kcal": 300, "protein_g": 12, "carbs_g": 40, "fat_g": 10,
    },
    {
        "name": "سەمبووسە", "emoji": "🥟",
        "aliases": ["Samosa", "sambousek", "fried pastry"],
        "kcal": 260, "protein_g": 7, "carbs_g": 28, "fat_g": 14,
    },
    {
        "name": "پەتاتەی سوورکراو", "emoji": "🍟",
        "aliases": ["french fries", "fried potato"],
        "kcal": 320, "protein_g": 4, "carbs_g": 42, "fat_g": 15,
    },
    {
        "name": "کۆرن دۆگ", "emoji": "🌭",
        "aliases": ["corn dog", "sausage on a stick"],
        "kcal": 340, "protein_g": 10, "carbs_g": 30, "fat_g": 20,
    },
    {
        "name": "کاولۆرمە", "emoji": "🌽",
        "aliases": ["grilled corn", "corn on the cob"],
        "kcal": 150, "protein_g": 5, "carbs_g": 32, "fat_g": 2,
    },

    # --- Restaurant meals --------------------------------------------
    {
        "name": "تیکەی مریشک", "emoji": "🍢",
        "aliases": ["chicken tikka", "chicken skewer"],
        "kcal": 350, "protein_g": 40, "carbs_g": 3, "fat_g": 18,
    },
    {
        "name": "کۆفتەی کوردی", "emoji": "🍖",
        "aliases": ["Kurdish kofta", "meatball skewer"],
        "kcal": 400, "protein_g": 28, "carbs_g": 8, "fat_g": 28,
    },
    {
        "name": "مەندی", "emoji": "🍛",
        "aliases": ["Mandi", "Yemeni-style rice and meat"],
        "kcal": 600, "protein_g": 35, "carbs_g": 60, "fat_g": 22,
    },
    {
        "name": "مەکلووبە", "emoji": "🍚",
        "aliases": ["Maqluba", "upside-down rice"],
        "kcal": 550, "protein_g": 25, "carbs_g": 65, "fat_g": 20,
    },

    # --- More vegetables & fruits --------------------------------------
    {
        "name": "کەلەم", "emoji": "🥬",
        "aliases": ["cabbage"],
        "kcal": 25, "protein_g": 1, "carbs_g": 6, "fat_g": 0,
    },
    {
        "name": "گەزەر", "emoji": "🥕",
        "aliases": ["carrot"],
        "kcal": 40, "protein_g": 1, "carbs_g": 10, "fat_g": 0,
    },
    {
        "name": "خواردنی زەردەلوو", "emoji": "🍑",
        "aliases": ["dried apricot", "zerdelu"],
        "kcal": 60, "protein_g": 1, "carbs_g": 15, "fat_g": 0,
    },
    {
        "name": "هەنجیر", "emoji": "🍈",
        "aliases": ["fig"],
        "kcal": 75, "protein_g": 1, "carbs_g": 19, "fat_g": 0,
    },
    {
        "name": "بەرقوق", "emoji": "🍑",
        "aliases": ["plum"],
        "kcal": 45, "protein_g": 1, "carbs_g": 11, "fat_g": 0,
    },

    # --- Sauces & condiments (more) -----------------------------------
    {
        "name": "مایۆنێز", "emoji": "🥫",
        "aliases": ["mayonnaise"],
        "kcal": 95, "protein_g": 0, "carbs_g": 1, "fat_g": 10,
    },
    {
        "name": "کێچەب", "emoji": "🍅",
        "aliases": ["ketchup"],
        "kcal": 20, "protein_g": 0, "carbs_g": 5, "fat_g": 0,
    },
    {
        "name": "سۆسی سیر", "emoji": "🧄",
        "aliases": ["garlic sauce", "toum"],
        "kcal": 150, "protein_g": 0, "carbs_g": 2, "fat_g": 16,
    },

    # --- Common brand-name snacks & drinks (recognized by package/logo) --
    # NOTE: per BRAND RECOGNITION in the prompt, these should be identified
    # by their actual printed name when the package is legible, not a
    # generic description - having them in the glossary reinforces that.
    {
        "name": "بیسکرێمی ئولکەر", "emoji": "🍫",
        "aliases": ["Ulker Biskrem", "Biskrem", "chocolate cream biscuit"],
        "kcal": 130, "protein_g": 2, "carbs_g": 16, "fat_g": 7,
    },
    {
        "name": "چیپسی لەیز", "emoji": "🍟",
        "aliases": ["Lays chips", "potato chips bag"],
        "kcal": 160, "protein_g": 2, "carbs_g": 15, "fat_g": 10,
    },
    {
        "name": "کۆکاکۆلا", "emoji": "🥤",
        "aliases": ["Coca-Cola", "Coke", "cola can or bottle"],
        "kcal": 140, "protein_g": 0, "carbs_g": 39, "fat_g": 0,
    },
    {
        "name": "پێپسی", "emoji": "🥤",
        "aliases": ["Pepsi"],
        "kcal": 150, "protein_g": 0, "carbs_g": 41, "fat_g": 0,
    },
    {
        "name": "نێستلێ کیتکات", "emoji": "🍫",
        "aliases": ["KitKat", "Nestle KitKat"],
        "kcal": 210, "protein_g": 3, "carbs_g": 27, "fat_g": 11,
    },
    {
        "name": "دانۆنی یۆگورت", "emoji": "🥛",
        "aliases": ["Danone yogurt", "Danonino"],
        "kcal": 90, "protein_g": 4, "carbs_g": 12, "fat_g": 3,
    },
]

# --- Commonly confused pairs -----------------------------------------
#
# Foods that look visually similar in a photo but are nutritionally
# different. Injected into the prompt so the model actively looks for the
# distinguishing visual cue instead of guessing - and if it genuinely
# can't tell, this is exactly when it should offer alternative estimates
# instead of picking one at random.
CONFUSABLE_PAIRS = [
    {
        "a": "سرکەی هەنار (پرتەقاڵی تاریک، سووکتر، شەفاف)",
        "b": "سۆسی تەماتە (سووری تۆخ، semi-opaque, تامی تەماتەیی)",
        "hint": "سرکەی هەنار زۆرجار تامی تووڕشتر و ڕەنگی تۆختر و شەفافترە، سۆسی تەماتە زیاتر سووری ڕوون و ئۆپەیکە",
    },
    {
        "a": "دۆو (سپی، شل، لە گلاسدا)",
        "b": "ماست (سپی، چڕ، لە کاسەدا)",
        "hint": "دۆو شلترە و زۆرجار لە گلاسێکدایە، ماست چڕترە و لە کاسەیەکدایە",
    },
    {
        "a": "کەرێ (زەردی کاڵ، سۆلید یان تواوە)",
        "b": "دۆنی زەیتوون (زەردی تۆخ یان سەوز، شل و درەوشاوە)",
        "hint": "کەرێ زۆرجار وەک پارچەیەکی سۆلید یان تواوە دیارە، دۆنی زەیتوون هەمیشە شلە و درەوشاوەیە",
    },
]


def build_confusable_prompt() -> str:
    lines = [f"- {p['a']} vs {p['b']}: {p['hint']}" for p in CONFUSABLE_PAIRS]
    return (
        "Pairs of foods that are easy to visually confuse - actively look "
        "for the distinguishing visual cue before deciding, and if you "
        "genuinely can't tell them apart, this is exactly the case where "
        "you should offer alternative estimates instead of guessing:\n"
        + "\n".join(lines)
    )


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


# --- Fuzzy matching -----------------------------------------------------
#
# Gemini sometimes identifies a food correctly but phrases it slightly
# differently than our glossary entry (e.g. "grilled chicken" vs our
# "Chicken" alias, or a minor spelling variation). This catches those
# cases in code, as a safety net independent of the model's own judgment,
# and re-labels the food with our canonical Kurdish name + emoji so the
# bot stays visually consistent no matter how Gemini phrased it.

import difflib


def _build_search_index():
    index = []
    for dish in KURDISH_FOOD_GLOSSARY:
        index.append((dish["name"].lower(), dish))
        for alias in dish["aliases"]:
            index.append((alias.lower(), dish))
    return index


_SEARCH_INDEX = _build_search_index()
_SEARCH_TERMS = [term for term, _ in _SEARCH_INDEX]


def find_glossary_match(name: str, cutoff: float = 0.6):
    """
    Fuzzy-matches a food name (Kurdish or English, whatever Gemini wrote)
    against every glossary name/alias. Returns the matched dish dict, or
    None if nothing is close enough.

    Checks substring containment first (catches short generic terms like
    "chicken" inside a longer alias like "Kurdish grilled chicken"), then
    falls back to a similarity ratio for spelling variations/typos.
    """
    query = (name or "").strip().lower()
    if not query or len(query) < 3:
        return None

    for term, dish in _SEARCH_INDEX:
        if query in term or term in query:
            return dish

    matches = difflib.get_close_matches(query, _SEARCH_TERMS, n=1, cutoff=cutoff)
    if not matches:
        return None

    matched_term = matches[0]
    for term, dish in _SEARCH_INDEX:
        if term == matched_term:
            return dish
    return None
