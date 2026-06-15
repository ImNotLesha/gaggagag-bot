import asyncio
import requests
import json
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

TOKEN = "8895997320:AAGKkIkm50B4aQUlDWuihyWtdTi2ZJ2WjR4"
API_URL = "https://grow-a-garden-2-tracker.onrender.com/api/stock"
REQUIRED_CHANNEL_ID = -1002506156473
REQUIRED_CHANNEL_LINK = "https://t.me/Ka1wex_rbx"

DATA_FILE = "user_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"subscribed_users": [], "blocked_groups": [], "tracked_plants": {}}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
subscribed_users = set(data.get("subscribed_users", []))
blocked_groups = set(data.get("blocked_groups", []))
tracked_plants = data.get("tracked_plants", {})

admin_ids = [5031974093, 1915569641]
last_stock_data = None
MOSCOW_TZ = timezone(timedelta(hours=3))

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def get_moscow_time():
    return datetime.now(MOSCOW_TZ)

PLANTS = [
    ("Carrot", "Common"), ("Strawberry", "Common"), ("Blueberry", "Common"),
    ("Tulip", "Uncommon"), ("Tomato", "Uncommon"), ("Apple", "Uncommon"),
    ("Bamboo", "Rare"), ("Corn", "Rare"), ("Cactus", "Rare"), ("Pineapple", "Rare"),
    ("Baby Cactus", "Rare"), ("Horned Melon", "Rare"), ("Mushroom", "Epic"),
    ("Green Bean", "Epic"), ("Banana", "Epic"), ("Grape", "Epic"), ("Coconut", "Epic"),
    ("Mango", "Epic"), ("Glow Mushroom", "Epic"), ("Dragon Fruit", "Legendary"),
    ("Acorn", "Legendary"), ("Cherry", "Legendary"), ("Sunflower", "Legendary"),
    ("Poison Ivy", "Legendary"), ("Venus Fly Trap", "Mythic"), ("Pomegranate", "Mythic"),
    ("Poison Apple", "Mythic"), ("Ghost Pepper", "Mythic"), ("Moon Bloom", "Super"),
    ("Dragon's Breath", "Super")
]

PLANT_EMOJIS = {
    "Carrot": "🥕", "Strawberry": "🍓", "Blueberry": "🫐", "Tulip": "🌷",
    "Tomato": "🍅", "Apple": "🍎", "Bamboo": "🎋", "Corn": "🌽", "Cactus": "🌵",
    "Pineapple": "🍍", "Baby Cactus": "🌵👶", "Horned Melon": "🥝", "Mushroom": "🍄",
    "Green Bean": "🟢", "Banana": "🍌", "Grape": "🍇", "Coconut": "🥥",
    "Mango": "🥭", "Glow Mushroom": "✨🍄", "Dragon Fruit": "🐉🍎", "Acorn": "🌰",
    "Cherry": "🍒", "Sunflower": "🌻", "Poison Ivy": "☠️🌿", "Venus Fly Trap": "🪴",
    "Pomegranate": "❤️🍎", "Poison Apple": "☠️🍎", "Ghost Pepper": "👻🌶️",
    "Moon Bloom": "🌙🌸", "Dragon's Breath": "🐉🔥"
}

RARE_RARITIES = ["Legendary", "Mythic", "Super"]

def get_plant_emoji(name):
    return PLANT_EMOJIS.get(name, "🌱")

def format_stock_message(data, rare_plant=None):
    moscow_time = get_moscow_time()
    msg = f"🌟 <b>Grow a Garden 2 — Сток обновился!</b> 🌟\n"
    msg += f"⏰ <i>{moscow_time.strftime('%H:%M:%S')} (МСК)</i>\n"
    msg += "─" * 25 + "\n\n"
    
    msg += "🌾 <b>СЕМЕНА</b>\n"
    has_items = False
    for item in data.get("shops", {}).get("SeedShop_Normal", []):
        if item.get("stock", 0) > 0:
            name = item.get('name', 'Unknown')
            stock = item.get('stock', 0)
            emoji = get_plant_emoji(name)
            msg += f"   {emoji} {name} — {stock} шт.\n"
            has_items = True
    if not has_items:
        msg += "   ❌ Нет в наличии\n"
    
    msg += "\n📦 <b>ЯЩИКИ</b>\n"
    has_items = False
    for item in data.get("shops", {}).get("CrateShop", []):
        if item.get("stock", 0) > 0:
            name = item.get('name', 'Unknown')
            stock = item.get('stock', 0)
            msg += f"   📦 {name} — {stock} шт.\n"
            has_items = True
    if not has_items:
        msg += "   ❌ Нет в наличии\n"
    
    msg += "\n⚙️ <b>СНАРЯЖЕНИЕ</b>\n"
    has_items = False
    for item in data.get("shops", {}).get("GearShop", []):
        if item.get("stock", 0) > 0:
            name = item.get('name', 'Unknown')
            stock = item.get('stock', 0)
            msg += f"   🔧 {name} — {stock} шт.\n"
            has_items = True
    if not has_items:
        msg += "   ❌ Нет в наличии\n"
    
    if rare_plant:
        msg += f"\n✨ <b>ВНИМАНИЕ! Появилось редкое растение: {rare_plant}!</b> ✨\n"
    
    msg += "\n" + "─" * 25 + "\n"
    msg += f"🔥 @Ka1wex_rbx"
    return msg

def format_urgent_message(plant_name):
    emoji = get_plant_emoji(plant_name)
    return (
        f"🚨 <b>ЭКСТРЕННОЕ УВЕДОМЛЕНИЕ!</b> 🚨\n\n"
        f"{emoji} <b>{plant_name}</b> появился в стоке!\n\n"
        f"🔥 <b>Срочно заходи в игру!</b>"
    )

async def check_channel_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

async def send_to_all(context, text, is_urgent=False, plant_name=None):
    for user_id in list(subscribed_users):
        try:
            if is_urgent:
                if str(user_id) in tracked_plants and plant_name in tracked_plants.get(str(user_id), []):
                    await context.bot.send_message(chat_id=user_id, text=text[:4096], parse_mode=ParseMode.HTML)
                    await asyncio.sleep(0.05)
            else:
                await context.bot.send_message(chat_id=user_id, text=text[:4096], parse_mode=ParseMode.HTML)
                await asyncio.sleep(0.05)
        except TelegramError:
            pass
    
    if not is_urgent:
        for group_id in blocked_groups:
            try:
                await context.bot.send_message(chat_id=group_id, text=text[:4096], parse_mode=ParseMode.HTML)
                await asyncio.sleep(0.05)
            except TelegramError:
                pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ Команда доступна только в личных сообщениях.")
        return
    
    if not await check_channel_subscription(user_id, context):
        keyboard = [[InlineKeyboardButton("📢 Подписаться на канал", url=REQUIRED_CHANNEL_LINK)]]
        await update.message.reply_text(
            f"❌ <b>{user_name}</b>, для использования бота нужно подписаться на канал!\n\n"
            f"🔗 <b>Канал:</b> {REQUIRED_CHANNEL_LINK}\n\n"
            f"После подписки нажмите /start снова",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return
    
    if user_id not in subscribed_users:
        subscribed_users.add(user_id)
        data["subscribed_users"] = list(subscribed_users)
        save_data()
    
    await update.message.reply_text(
        f"✨ <b>Добро пожаловать, {user_name}!</b> ✨\n\n"
        "🌱 Вы подписаны на уведомления о стоке!\n\n"
        "📋 <b>Команды:</b>\n"
        "   /start — подписаться\n"
        "   /end — отписаться\n"
        "   /live — текущий сток\n"
        "   /look — отслеживать растения\n"
        "   /mylook — мои растения\n"
        "   /unlook — очистить отслеживание\n\n"
        "🔥 <b>@Ka1wex_rbx</b>",
        parse_mode=ParseMode.HTML
    )

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ Команда доступна только в личных сообщениях.")
        return
    
    if user_id in subscribed_users:
        subscribed_users.remove(user_id)
        data["subscribed_users"] = list(subscribed_users)
        save_data()
        await update.message.reply_text(f"❌ {user_name}, вы отписаны от уведомлений.")
    else:
        await update.message.reply_text("ℹ️ Вы не были подписаны.")

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ Команда доступна только в личных сообщениях.")
        return
    
    if not await check_channel_subscription(user_id, context):
        keyboard = [[InlineKeyboardButton("📢 Подписаться на канал", url=REQUIRED_CHANNEL_LINK)]]
        await update.message.reply_text(
            "❌ Подпишитесь на канал чтобы использовать /live",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    await update.message.reply_text("📡 Получаю данные...")
    try:
        resp = requests.get(API_URL, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            msg = format_stock_message(data)
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Не удалось получить данные")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

def get_look_keyboard(page=0):
    items_per_page = 4
    total_pages = (len(PLANTS) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = min(start + items_per_page, len(PLANTS))
    
    keyboard = []
    for i in range(start, end, 2):
        row = []
        for j in range(2):
            if i + j < end:
                plant, rarity = PLANTS[i + j]
                emoji = get_plant_emoji(plant)
                row.append(InlineKeyboardButton(f"{emoji} {plant}", callback_data=f"toggle_{plant}"))
        keyboard.append(row)
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"page_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="none"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"page_{page + 1}"))
    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("✅ Подтвердить выбор", callback_data="confirm_look")])
    
    return InlineKeyboardMarkup(keyboard)

async def look(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ Команда доступна только в личных сообщениях.")
        return
    
    if not await check_channel_subscription(int(user_id), context):
        keyboard = [[InlineKeyboardButton("📢 Подписаться на канал", url=REQUIRED_CHANNEL_LINK)]]
        await update.message.reply_text("❌ Подпишитесь на канал чтобы использовать /look", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    context.user_data['look_page'] = 0
    context.user_data['temp_selected'] = tracked_plants.get(user_id, []).copy()
    
    msg = "🌱 <b>Выберите растения для отслеживания:</b>\n\n"
    msg += "✅ — уже отслеживается\n"
    msg += "Нажмите на растение чтобы добавить/удалить\n\n"
    msg += "🔥 <b>@Ka1wex_rbx</b>"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=get_look_keyboard(0))

async def mylook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ Команда доступна только в личных сообщениях.")
        return
    
    plants = tracked_plants.get(user_id, [])
    if not plants:
        await update.message.reply_text("🌱 Вы не отслеживаете ни одного растения.\n\nИспользуйте /look чтобы добавить.")
        return
    
    msg = "🌱 <b>Ваши отслеживаемые растения:</b>\n\n"
    for plant in plants:
        emoji = get_plant_emoji(plant)
        msg += f"{emoji} {plant}\n"
    msg += f"\n🔥 @Ka1wex_rbx"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def unlook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ Команда доступна только в личных сообщениях.")
        return
    
    if user_id in tracked_plants:
        del tracked_plants[user_id]
        data["tracked_plants"] = tracked_plants
        save_data()
        await update.message.reply_text("✅ Вы отписаны от отслеживания всех растений.")
    else:
        await update.message.reply_text("ℹ️ Вы не отслеживали ни одного растения.")

async def stopgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Команда доступна только в группах.")
        return
    
    if chat_id in blocked_groups:
        await update.message.reply_text("ℹ️ Уведомления в этой группе уже отключены.")
        return
    
    blocked_groups.add(chat_id)
    data["blocked_groups"] = list(blocked_groups)
    save_data()
    await update.message.reply_text("❌ Уведомления о стоке в этой группе отключены.\nДля включения используйте /startgroup")

async def startgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Команда доступна только в группах.")
        return
    
    if chat_id not in blocked_groups:
        await update.message.reply_text("ℹ️ Уведомления в этой группе уже включены.")
        return
    
    blocked_groups.remove(chat_id)
    data["blocked_groups"] = list(blocked_groups)
    save_data()
    await update.message.reply_text("✅ Уведомления о стоке в этой группе включены.\nДля отключения используйте /stopgroup")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data_callback = query.data
    
    if data_callback.startswith("page_"):
        page = int(data_callback.split("_")[1])
        context.user_data['look_page'] = page
        await query.edit_message_reply_markup(reply_markup=get_look_keyboard(page))
        return
    
    if data_callback.startswith("toggle_"):
        plant = data_callback.replace("toggle_", "")
        temp = context.user_data.get('temp_selected', [])
        if plant in temp:
            temp.remove(plant)
        else:
            temp.append(plant)
        context.user_data['temp_selected'] = temp
        
        page = context.user_data.get('look_page', 0)
        await query.edit_message_reply_markup(reply_markup=get_look_keyboard(page))
        return
    
    if data_callback == "confirm_look":
        temp = context.user_data.get('temp_selected', [])
        if temp:
            tracked_plants[user_id] = temp
        elif user_id in tracked_plants:
            del tracked_plants[user_id]
        data["tracked_plants"] = tracked_plants
        save_data()
        
        await query.edit_message_text(
            f"✅ Выбранные растения сохранены!\n\n" + "\n".join([f"{get_plant_emoji(p)} {p}" for p in temp]) if temp else "🌱 Вы не выбрали ни одного растения.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if data_callback == "none":
        await query.answer()

async def check_stock(context: ContextTypes.DEFAULT_TYPE):
    global last_stock_data
    try:
        resp = requests.get(API_URL, timeout=15)
        if resp.status_code != 200:
            return
        
        new_data = resp.json()
        
        if last_stock_data is None:
            last_stock_data = new_data
            return
        
        old_seeds = {}
        new_seeds = {}
        for item in last_stock_data.get("shops", {}).get("SeedShop_Normal", []):
            old_seeds[item.get("name")] = item.get("stock", 0)
        for item in new_data.get("shops", {}).get("SeedShop_Normal", []):
            new_seeds[item.get("name")] = item.get("stock", 0)
        
        if old_seeds != new_seeds:
            changed_plants = []
            rare_plants = []
            for name, stock in new_seeds.items():
                if stock > 0 and old_seeds.get(name, 0) == 0:
                    changed_plants.append(name)
                    for plant, rarity in PLANTS:
                        if plant == name and rarity in RARE_RARITIES:
                            rare_plants.append(name)
            
            stock_msg = format_stock_message(new_data, rare_plants[0] if rare_plants else None)
            await send_to_all(context, stock_msg)
            
            for plant in changed_plants:
                for uid, plants in tracked_plants.items():
                    if plant in plants:
                        try:
                            urgent_msg = format_urgent_message(plant)
                            await context.bot.send_message(chat_id=int(uid), text=urgent_msg, parse_mode=ParseMode.HTML)
                            await asyncio.sleep(0.05)
                        except:
                            pass
            
            last_stock_data = new_data
            
    except Exception as e:
        print(f"Ошибка: {e}")

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("end", end))
    application.add_handler(CommandHandler("live", live))
    application.add_handler(CommandHandler("look", look))
    application.add_handler(CommandHandler("mylook", mylook))
    application.add_handler(CommandHandler("unlook", unlook))
    application.add_handler(CommandHandler("stopgroup", stopgroup))
    application.add_handler(CommandHandler("startgroup", startgroup))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(check_stock, interval=15, first=5)
        print("⏰ Проверка стока: раз в 15 секунд")
    
    print("🤖 Бот запущен!")
    print(f"👥 Подписчиков: {len(subscribed_users)}")
    print(f"🚫 Заблокированных групп: {len(blocked_groups)}")
    print(f"🌱 Пользователей с отслеживанием: {len(tracked_plants)}")
    print("🔥 @Ka1wex_rbx")
    application.run_polling()

if __name__ == "__main__":
    main()