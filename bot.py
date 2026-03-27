import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import aiosqlite

from config import *

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

DB_PATH = "database.db"

# ==================== БАЗА ДАННЫХ ====================

async def init_db():
    """Создание таблиц"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_paid INTEGER DEFAULT 0,
                participant_number INTEGER,
                paid_at TIMESTAMP,
                payment_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    """Получить пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def add_user(user: types.User):
    """Добавить пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
        """, (user.id, user.username, user.full_name))
        await db.commit()

async def get_next_participant_number():
    """Получить следующий номер участника"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT MAX(participant_number) FROM users WHERE is_paid = 1") as cursor:
            result = await cursor.fetchone()
            return (result[0] or 0) + 1

async def mark_user_paid(user_id: int, payment_id: str = None):
    """Отметить пользователя как оплатившего"""
    number = await get_next_participant_number()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET is_paid = 1, participant_number = ?, paid_at = ?, payment_id = ?
            WHERE user_id = ?
        """, (number, datetime.now(), payment_id, user_id))
        await db.commit()
    return number

async def get_all_users():
    """Получить всех пользователей"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            return await cursor.fetchall()

async def get_paid_users():
    """Получить оплативших"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_paid = 1") as cursor:
            return await cursor.fetchall()

async def get_stats():
    """Статистика"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_paid = 1") as cursor:
            paid = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE DATE(registered_at) = DATE('now')") as cursor:
            today = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_paid = 1 AND DATE(paid_at) = DATE('now')") as cursor:
            paid_today = (await cursor.fetchone())[0]
    return {"total": total, "paid": paid, "today": today, "paid_today": paid_today}

# ==================== ПРОВЕРКИ ====================

def is_admin(user_id: int) -> bool:
    """Проверка на админа"""
    return user_id in ADMINS

def is_main_admin(user_id: int) -> bool:
    """Проверка на главного админа"""
    return len(ADMINS) > 0 and user_id == ADMINS[0]

# ==================== КЛАВИАТУРЫ ====================

def get_main_keyboard():
    """Главная клавиатура выбора канала"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_OPEN_CHANNEL, callback_data="open_channel")],
        [InlineKeyboardButton(text=BTN_CLOSED_CHANNEL, callback_data="closed_channel")]
    ])

def get_open_channel_keyboard():
    """Клавиатура открытого канала"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Перейти в канал", url=OPEN_CHANNEL_URL)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])

def get_payment_keyboard():
    """Клавиатура оплаты через Lava Top Mini App"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=BTN_PAY.format(price=PRICE),
            web_app=WebAppInfo(url=LAVA_TOP_URL)
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])

async def get_success_keyboard(user_id: int):
    """Клавиатура после оплаты с инвайт-ссылкой"""
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CLOSED_CHANNEL_ID,
            member_limit=1,
            name=f"User {user_id}"
        )
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BTN_JOIN_CLOSED, url=invite.invite_link)]
        ])
    except Exception as e:
        logger.error(f"Ошибка создания инвайта: {e}")
        return None

# ==================== ХЕНДЛЕРЫ ====================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Команда /start"""
    await add_user(message.from_user)
    
    # Проверяем, не оплатил ли уже
    user = await get_user(message.from_user.id)
    if user and user["is_paid"]:
        kb = await get_success_keyboard(message.from_user.id)
        await message.answer(
            PAYMENT_SUCCESS_TEXT.format(number=user["participant_number"]),
            reply_markup=kb
        )
        return
    
    # Отправляем видео (если есть) + приветствие
    # TODO: Добавить отправку видео когда будет готово
    # await message.answer_video(video="FILE_ID_OR_URL", caption=WELCOME_TEXT, reply_markup=get_main_keyboard())
    
    await message.answer(WELCOME_TEXT, reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "open_channel")
async def cb_open_channel(callback: types.CallbackQuery):
    """Открытый канал"""
    await callback.message.edit_text(
        OPEN_CHANNEL_TEXT,
        reply_markup=get_open_channel_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "closed_channel")
async def cb_closed_channel(callback: types.CallbackQuery):
    """Закрытый канал — оплата"""
    # Проверяем, не оплатил ли уже
    user = await get_user(callback.from_user.id)
    if user and user["is_paid"]:
        kb = await get_success_keyboard(callback.from_user.id)
        await callback.message.edit_text(
            PAYMENT_SUCCESS_TEXT.format(number=user["participant_number"]),
            reply_markup=kb
        )
        await callback.answer("Ты уже оплатил! ✅")
        return
    
    await callback.message.edit_text(
        CLOSED_CHANNEL_TEXT.format(price=PRICE),
        reply_markup=get_payment_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def cb_back(callback: types.CallbackQuery):
    """Назад к выбору"""
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=get_main_keyboard())
    await callback.answer()

# ==================== АДМИН КОМАНДЫ ====================

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Статистика"""
    if not is_admin(message.from_user.id):
        return
    
    stats = await get_stats()
    text = f"""📊 <b>Статистика бота</b>

👥 Всего пользователей: <b>{stats['total']}</b>
💰 Оплатили: <b>{stats['paid']}</b>
📈 Конверсия: <b>{round(stats['paid']/stats['total']*100, 1) if stats['total'] > 0 else 0}%</b>

📅 <b>Сегодня:</b>
🆕 Новых: {stats['today']}
💳 Оплат: {stats['paid_today']}"""
    
    await message.answer(text)

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    """Рассылка всем"""
    if not is_admin(message.from_user.id):
        return
    
    # Получаем текст после команды
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("❌ Укажи текст рассылки:\n<code>/broadcast Твой текст</code>")
        return
    
    users = await get_all_users()
    sent = 0
    failed = 0
    
    status_msg = await message.answer(f"📤 Начинаю рассылку для {len(users)} пользователей...")
    
    for user in users:
        try:
            await bot.send_message(user["user_id"], text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Антифлуд
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n\n📨 Отправлено: {sent}\n❌ Ошибок: {failed}")

@dp.message(Command("broadcast_paid"))
async def cmd_broadcast_paid(message: types.Message):
    """Рассылка только оплатившим"""
    if not is_admin(message.from_user.id):
        return
    
    text = message.text.replace("/broadcast_paid", "").strip()
    if not text:
        await message.answer("❌ Укажи текст:\n<code>/broadcast_paid Твой текст</code>")
        return
    
    users = await get_paid_users()
    sent = 0
    
    for user in users:
        try:
            await bot.send_message(user["user_id"], text)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    
    await message.answer(f"✅ Отправлено {sent} оплатившим участникам")

@dp.message(Command("add_admin"))
async def cmd_add_admin(message: types.Message):
    """Добавить админа"""
    if not is_main_admin(message.from_user.id):
        await message.answer("❌ Только главный админ может добавлять админов")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажи ID:\n<code>/add_admin 123456789</code>")
        return
    
    try:
        new_admin_id = int(args[1])
        if new_admin_id not in ADMINS:
            ADMINS.append(new_admin_id)
            await message.answer(f"✅ Админ {new_admin_id} добавлен")
        else:
            await message.answer("⚠️ Уже админ")
    except ValueError:
        await message.answer("❌ ID должен быть числом")

@dp.message(Command("admins"))
async def cmd_admins(message: types.Message):
    """Список админов"""
    if not is_admin(message.from_user.id):
        return
    
    text = "👑 <b>Админы бота:</b>\n\n"
    for i, admin_id in enumerate(ADMINS):
        role = "👑 Главный" if i == 0 else "👤 Админ"
        text += f"{role}: <code>{admin_id}</code>\n"
    
    await message.answer(text)

@dp.message(Command("set_video"))
async def cmd_set_video(message: types.Message):
    """Установить видео (ответом на видео)"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.answer("❌ Ответь этой командой на видео которое хочешь установить")
        return
    
    video_id = message.reply_to_message.video.file_id
    # Сохраняем в базу
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('welcome_video', ?)", (video_id,))
        await db.commit()
    
    await message.answer(f"✅ Видео установлено!\nFile ID: <code>{video_id}</code>")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Помощь для админов"""
    if not is_admin(message.from_user.id):
        return
    
    text = """🔧 <b>Команды админа:</b>

📊 <b>Статистика:</b>
/stats — общая статистика

📤 <b>Рассылки:</b>
/broadcast текст — всем
/broadcast_paid текст — только оплатившим

⚙️ <b>Настройки:</b>
/set_video — ответь на видео
/admins — список админов
/add_admin ID — добавить админа

💳 <b>Платежи:</b>
/confirm ID — подтвердить оплату вручную"""
    
    await message.answer(text)

@dp.message(Command("confirm"))
async def cmd_confirm(message: types.Message):
    """Ручное подтверждение оплаты"""
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажи ID пользователя:\n<code>/confirm 123456789</code>")
        return
    
    try:
        user_id = int(args[1])
        user = await get_user(user_id)
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if user["is_paid"]:
            await message.answer(f"⚠️ Уже оплачен. Номер: #{user['participant_number']}")
            return
        
        number = await mark_user_paid(user_id, "manual_confirm")
        
        # Отправляем пользователю
        try:
            kb = await get_success_keyboard(user_id)
            await bot.send_message(
                user_id,
                PAYMENT_SUCCESS_TEXT.format(number=number),
                reply_markup=kb
            )
        except Exception:
            pass
        
        await message.answer(f"✅ Оплата подтверждена!\nПользователь: {user_id}\nНомер: #{number}")
        
    except ValueError:
        await message.answer("❌ ID должен быть числом")

# ==================== ВЕБХУК LAVA TOP ====================

# Этот эндпоинт будет обрабатывать вебхуки от Lava Top
# Для работы нужно поднять веб-сервер (см. webhook_server.py)

async def process_lava_payment(user_id: int, payment_id: str):
    """Обработка успешного платежа от Lava Top"""
    user = await get_user(user_id)
    if not user:
        logger.error(f"User {user_id} not found for payment {payment_id}")
        return False
    
    if user["is_paid"]:
        logger.info(f"User {user_id} already paid")
        return True
    
    number = await mark_user_paid(user_id, payment_id)
    
    # Отправляем сообщение об успехе
    try:
        kb = await get_success_keyboard(user_id)
        await bot.send_message(
            user_id,
            PAYMENT_SUCCESS_TEXT.format(number=number),
            reply_markup=kb
        )
        logger.info(f"User {user_id} paid successfully, number #{number}")
    except Exception as e:
        logger.error(f"Failed to send success message to {user_id}: {e}")
    
    return True

# ==================== ЗАПУСК ====================

async def main():
    await init_db()
    logger.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
