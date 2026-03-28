# ===== НАСТРОЙКИ БОТА =====
# Меняй значения здесь или через команды /set_*
 
# Токен бота (получаешь в @BotFather)
BOT_TOKEN = "8785851144:AAE2uktmKVHWmn_fds5jpDqxwYB6-yKTpao"
 
# Админы (твой ID первый = главный админ)
ADMINS = [
    714403607,  # @novusordoselcorum - главный админ
]
 
# === КАНАЛЫ ===
OPEN_CHANNEL_URL = "https://t.me/aziznabmw"  # Открытый канал
CLOSED_CHANNEL_ID = -1003519289043  # Закрытый канал BMW
 
# === ОПЛАТА ===
LAVA_TOP_URL = "https://app.lava.top/ru/products/ca4c6acc-490a-46c2-9035-063d31263d15?currency=RUB"
LAVA_SECRET_KEY = "bmw-secret-2026"  # Ключ для проверки вебхуков
PRICE = 1000  # Цена в рублях
 
# === ТЕКСТЫ ===
WELCOME_TEXT = """🎁 <b>Добро пожаловать!</b>
 
Выбери свой путь:
👇👇👇"""
 
OPEN_CHANNEL_TEXT = """🔓 <b>Открытый канал</b>
 
Переходи по ссылке и присоединяйся:"""
 
CLOSED_CHANNEL_TEXT = """🔐 <b>Закрытый канал</b>
 
Стоимость: <b>{price}₽</b> (разовый платёж)
 
Нажми кнопку ниже для оплаты 👇"""
 
PAYMENT_SUCCESS_TEXT = """🎉 <b>Оплата прошла успешно!</b>
 
Твой номер: <b>#{number}</b>
 
Добро пожаловать в закрытый канал 👇"""
 
# === КНОПКИ ===
BTN_OPEN_CHANNEL = "🔓 Открытый канал"
BTN_CLOSED_CHANNEL = "🔐 Закрытый канал"
BTN_PAY = "💳 Оплатить {price}₽"
BTN_JOIN_CLOSED = "🚀 Войти в закрытый канал"
