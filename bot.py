import logging
import asyncio
import os
import database
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

GENDER, AGE, WEIGHT, HEIGHT, ACTIVITY, GOAL = range(6)

ACTIVITY_LEVELS = {
    "🛋 Sedentary": {
        "multiplier": 1.2,
        "description": "Desk job, little to no exercise"
    },
    "🚶 Lightly active": {
        "multiplier": 1.375,
        "description": "Light workouts 1-3 days a week"
    },
    "🏃 Moderately active": {
        "multiplier": 1.55,
        "description": "Workouts 3-5 days a week"
    },
    "💪 Very active": {
        "multiplier": 1.725,
        "description": "Intense training 6-7 days a week"
    },
    "🏋 Extremely active": {
        "multiplier": 1.9,
        "description": "Pro sports, physical job + training"
    },
}

GOALS = {
    "⬇️ Lose weight": -500,
    "⚖️ Maintain weight": 0,
    "⬆️ Gain muscle": +300,
    "💥 Bulk (aggressive)": +500,
}

STEP_ORDER = [GENDER, AGE, WEIGHT, HEIGHT, ACTIVITY, GOAL]
STEP_NAMES = {
    GENDER:   "gender",
    AGE:      "age",
    WEIGHT:   "weight",
    HEIGHT:   "height",
    ACTIVITY: "activity",
    GOAL:     "goal",
}


def nav_keyboard(keys: list) -> ReplyKeyboardMarkup:
    """Builds a keyboard with nav buttons appended at the bottom."""
    nav_row = ["🔄 Restart", "⬅️ Back"]
    return ReplyKeyboardMarkup(
        keys + [nav_row],
        one_time_keyboard=True,
        resize_keyboard=True
    )


def nav_keyboard_text() -> ReplyKeyboardMarkup:
    """Nav-only keyboard for text-input steps (age, weight, height)."""
    return ReplyKeyboardMarkup(
        [["🔄 Restart", "⬅️ Back"]],
        one_time_keyboard=False,
        resize_keyboard=True
    )


def is_restart(text: str) -> bool:
    return text == "🔄 Restart"


def is_back(text: str) -> bool:
    return text == "⬅️ Back"


def calculate_bmr(gender: str, age: int, weight: float, height: float) -> float:
    bmr = (10 * weight) + (6.25 * height) - (5 * age)
    if gender == "male":
        bmr += 5
    else:
        bmr -= 161
    return bmr


def calculate_tdee(bmr: float, activity_key: str) -> float:
    multiplier = ACTIVITY_LEVELS[activity_key]["multiplier"]
    return bmr * multiplier


def calculate_macros(calories: float, goal_key: str) -> dict:
    protein_cals = calories * 0.30
    fat_cals     = calories * 0.25
    carb_cals    = calories * 0.45
    return {
        "protein": round(protein_cals / 4),
        "fat":     round(fat_cals / 9),
        "carbs":   round(carb_cals / 4),
    }


def calculate_water(weight: float, activity_key: str) -> float:
    base = weight * 35
    multiplier = ACTIVITY_LEVELS[activity_key]["multiplier"]
    if multiplier >= 1.725:
        base += 700
    elif multiplier >= 1.55:
        base += 400
    elif multiplier >= 1.375:
        base += 200
    return round(base / 1000, 1)


def format_result(user_data: dict) -> str:
    gender       = user_data["gender"]
    age          = user_data["age"]
    weight       = user_data["weight"]
    height       = user_data["height"]
    activity_key = user_data["activity"]
    goal_key     = user_data["goal"]

    bmr           = calculate_bmr(gender, age, weight, height)
    tdee          = calculate_tdee(bmr, activity_key)
    goal_calories = tdee + GOALS[goal_key]
    macros        = calculate_macros(goal_calories, goal_key)
    water         = calculate_water(weight, activity_key)
    gender_icon   = "👨" if gender == "male" else "👩"

    result = f"""
🏋️ *Your results, {gender_icon}*

📊 *Your stats:*
├ Age: {age} years
├ Weight: {weight} kg
├ Height: {height} cm
├ Activity: {activity_key}
└ Goal: {goal_key}

🔥 *Calories:*
├ Basal Metabolic Rate (BMR): *{round(bmr)} kcal/day*
├ With activity (TDEE): *{round(tdee)} kcal/day*
└ Your target: *{round(goal_calories)} kcal/day* ⬅️

🥩 *Daily macros:*
├ 🥚 Protein: *{macros["protein"]} g* ({round(macros["protein"] * 4)} kcal)
├ 🥑 Fat: *{macros["fat"]} g* ({round(macros["fat"] * 9)} kcal)
└ 🍚 Carbs: *{macros["carbs"]} g* ({round(macros["carbs"] * 4)} kcal)

💧 *Daily water intake: {water} L*

💡 *What this means:*
"""

    if goal_key == "⬇️ Lose weight":
        result += "A 500 kcal deficit means roughly *-0.5 kg per week* — safe and steady."
    elif goal_key == "⚖️ Maintain weight":
        result += "Eat this amount and your weight stays stable. Perfect for body recomposition."
    elif goal_key == "⬆️ Gain muscle":
        result += "A 300 kcal surplus means slow, clean muscle gain with minimal fat."
    elif goal_key == "💥 Bulk (aggressive)":
        result += "A 500 kcal surplus means fast mass gain — great for hardgainers."

    result += "\n\n📌 Press /start or 🔄 Restart to recalculate."
    return result


async def ask_gender(update: Update) -> int:
    keyboard = nav_keyboard([["👨 Male", "👩 Female"]])
    await update.message.reply_text(
        "👋 Hey! I'm *FitCalc* — your personal calorie calculator.\n\n"
        "In 30 seconds I'll calculate:\n"
        "✅ Your daily calorie target\n"
        "✅ Protein, fat and carbs\n"
        "✅ Daily water intake\n\n"
        "Let's go! *Select your gender:*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    return GENDER


async def ask_age(update: Update) -> int:
    await update.message.reply_text(
        "💪 Great! Now *how old are you?*\n\n"
        "_(just type a number, e.g. 22)_",
        parse_mode="Markdown",
        reply_markup=nav_keyboard_text()
    )
    return AGE


async def ask_weight(update: Update) -> int:
    await update.message.reply_text(
        "⚖️ Got it! Now *your weight in kg?*\n\n"
        "_(decimals are fine: 75.5)_",
        parse_mode="Markdown",
        reply_markup=nav_keyboard_text()
    )
    return WEIGHT


async def ask_height(update: Update) -> int:
    await update.message.reply_text(
        "📏 Almost there! *Your height in cm?*\n\n"
        "_(e.g. 180)_",
        parse_mode="Markdown",
        reply_markup=nav_keyboard_text()
    )
    return HEIGHT


async def ask_activity(update: Update) -> int:
    descriptions = "\n".join([
        f"{key} — {val['description']}"
        for key, val in ACTIVITY_LEVELS.items()
    ])
    keyboard = nav_keyboard([[level] for level in ACTIVITY_LEVELS.keys()])
    await update.message.reply_text(
        f"🏃 *Choose your activity level:*\n\n{descriptions}",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    return ACTIVITY


async def ask_goal(update: Update) -> int:
    keyboard = nav_keyboard([[goal] for goal in GOALS.keys()])
    await update.message.reply_text(
        "🎯 *Last question — what's your goal?*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    return GOAL


ASK_STEP = {
    GENDER:   ask_gender,
    AGE:      ask_age,
    WEIGHT:   ask_weight,
    HEIGHT:   ask_height,
    ACTIVITY: ask_activity,
    GOAL:     ask_goal,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    user = update.effective_user
    database.add_or_update_user(user.id, user.username, user.first_name)
    context.user_data["current_step"] = GENDER
    return await ask_gender(update)


async def back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    current = context.user_data.get("current_step", GENDER)
    prev = current - 1

    if prev < GENDER:
        await update.message.reply_text("⚠️ You're already at the first step!")
        return await ask_gender(update)

    field = STEP_NAMES.get(prev)
    if field and field in context.user_data:
        del context.user_data[field]

    context.user_data["current_step"] = prev
    return await ASK_STEP[prev](update)


async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if is_restart(text):
        return await start(update, context)
    if is_back(text):
        return await back(update, context)

    context.user_data["gender"] = "male" if "Male" in text else "female"
    context.user_data["current_step"] = AGE
    return await ask_age(update)


async def age_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if is_restart(text):
        return await start(update, context)
    if is_back(text):
        return await back(update, context)

    try:
        age = int(text)
        if age < 10 or age > 100:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter an age between 10 and 100, e.g. *22*",
            parse_mode="Markdown",
            reply_markup=nav_keyboard_text()
        )
        return AGE

    context.user_data["age"] = age
    context.user_data["current_step"] = WEIGHT
    return await ask_weight(update)


async def weight_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if is_restart(text):
        return await start(update, context)
    if is_back(text):
        return await back(update, context)

    try:
        weight = float(text.replace(",", "."))
        if weight < 30 or weight > 300:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter a weight between 30 and 300, e.g. *75.5*",
            parse_mode="Markdown",
            reply_markup=nav_keyboard_text()
        )
        return WEIGHT

    context.user_data["weight"] = weight
    context.user_data["current_step"] = HEIGHT
    return await ask_height(update)


async def height_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if is_restart(text):
        return await start(update, context)
    if is_back(text):
        return await back(update, context)

    try:
        height = float(text.replace(",", "."))
        if height < 100 or height > 250:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter a height between 100 and 250, e.g. *180*",
            parse_mode="Markdown",
            reply_markup=nav_keyboard_text()
        )
        return HEIGHT

    context.user_data["height"] = height
    context.user_data["current_step"] = ACTIVITY
    return await ask_activity(update)


async def activity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if is_restart(text):
        return await start(update, context)
    if is_back(text):
        return await back(update, context)

    if text not in ACTIVITY_LEVELS:
        await update.message.reply_text(
            "⚠️ Please choose one of the options on the keyboard below.",
            reply_markup=nav_keyboard([[level] for level in ACTIVITY_LEVELS.keys()])
        )
        return ACTIVITY

    context.user_data["activity"] = text
    context.user_data["current_step"] = GOAL
    return await ask_goal(update)


async def goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if is_restart(text):
        return await start(update, context)
    if is_back(text):
        return await back(update, context)

    if text not in GOALS:
        await update.message.reply_text(
            "⚠️ Please choose one of the options on the keyboard below.",
            reply_markup=nav_keyboard([[goal] for goal in GOALS.keys()])
        )
        return GOAL

    context.user_data["goal"] = text

    user_data = context.user_data
    bmr = calculate_bmr(user_data["gender"], user_data["age"], 
                       user_data["weight"], user_data["height"])
    tdee = calculate_tdee(bmr, user_data["activity"])
    target_calories = tdee + GOALS[user_data["goal"]]
    
    # Save to DB
    database.save_calculation(
        update.effective_user.id,
        {
            **user_data,
            'bmr': bmr,
            'tdee': tdee,
            'target_calories': target_calories
        }
    )
    result = format_result(context.user_data)
    await update.message.reply_text(
        result,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [["🔄 Restart"]],
            resize_keyboard=True
        )
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "❌ Calculation cancelled. Type /start to begin again.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏋️ *FitCalc Bot* — calorie calculator for athletes\n\n"
        "📌 *Commands:*\n"
        "/start — start a new calculation\n"
        "/back — go to the previous step\n"
        "/help — show this help message\n"
        "/stats — view bot statistics\n"
        "/cancel — cancel the current calculation\n\n"
        "📊 *What I calculate:*\n"
        "• BMR — Basal Metabolic Rate\n"
        "• TDEE — Total Daily Energy Expenditure\n"
        "• Protein, fat and carbs\n"
        "• Daily water intake\n\n"
        "🧮 *Formula:* Mifflin-St Jeor (most accurate for athletes)\n\n"
        "Type /start to begin! 💪",
        parse_mode="Markdown"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    stats = database.get_user_stats()
    
    top_goals_text = "\n".join([
        f"  • {goal}: {count} users"
        for goal, count in stats['top_goals'][:3]
    ]) if stats['top_goals'] else "  No data yet"
    
    top_activities_text = "\n".join([
        f"  • {activity}: {count} users"
        for activity, count in stats['top_activities'][:3]
    ]) if stats['top_activities'] else "  No data yet"
    
    message = f"""
📊 *FitCalc Statistics*

👥 *Users:* {stats['total_users']} registered
🧮 *Calculations:* {stats['total_calculations']} total

📈 *Averages:*
├ Age: {stats['avg_age']} years
├ Weight: {stats['avg_weight']} kg
└ Height: {stats['avg_height']} cm

🎯 *Popular goals:*
{top_goals_text}

🏃 *Activity levels:*
{top_activities_text}
"""
    
    await update.message.reply_text(message, parse_mode="Markdown")





async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env file!")
        print("Create a .env file and add: TELEGRAM_BOT_TOKEN=your_token")
        return

    database.init_db()



    app = Application.builder().token(token).build()

    nav_filter = filters.TEXT & ~filters.COMMAND

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Text(["🔄 Restart"]), start),
        ],
        states={
            GENDER:   [MessageHandler(nav_filter, gender_handler)],
            AGE:      [MessageHandler(nav_filter, age_handler)],
            WEIGHT:   [MessageHandler(nav_filter, weight_handler)],
            HEIGHT:   [MessageHandler(nav_filter, height_handler)],
            ACTIVITY: [MessageHandler(nav_filter, activity_handler)],
            GOAL:     [MessageHandler(nav_filter, goal_handler)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("back", back),
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))

    print("✅ FitCalc Bot is running!")
    print("Open Telegram and send /start to your bot")
    print("Press Ctrl+C to stop")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    print("Bot is live! Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        print("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())