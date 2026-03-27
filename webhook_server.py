"""
Веб-сервер для приёма вебхуков от Lava Top
Запускается вместе с ботом на Railway
"""
 
import asyncio
import hashlib
import hmac
import json
import logging
from aiohttp import web
 
from config import LAVA_SECRET_KEY
from bot import process_lava_payment, bot, init_db
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
def verify_webhook(request) -> bool:
    """Проверка API ключа в заголовке X-Api-Key"""
    api_key = request.headers.get("X-Api-Key", "")
    
    if not LAVA_SECRET_KEY:
        logger.warning("LAVA_SECRET_KEY not set, skipping verification")
        return True
    
    return api_key == LAVA_SECRET_KEY
 
async def handle_lava_webhook(request: web.Request) -> web.Response:
    """Обработчик вебхука от Lava Top"""
    try:
        # Проверяем API ключ
        if not verify_webhook(request):
            logger.warning("Invalid webhook API key")
            return web.Response(status=403, text="Invalid API key")
        
        # Получаем данные
        data = await request.read()
        
        # Парсим JSON
        payload = json.loads(data)
        logger.info(f"Lava webhook received: {payload}")
        
        # Извлекаем данные по документации Lava Top
        event_type = payload.get("type")
        
        if event_type == "payment.success":
            # Получаем email покупателя и ищем по нему
            buyer_email = payload.get("buyerEmail")
            contract_id = payload.get("contractId")
            
            # customFields может содержать user_id если передали при создании
            custom_fields = payload.get("customFields", {})
            user_id = custom_fields.get("user_id") or custom_fields.get("telegram_id")
            
            if user_id:
                await process_lava_payment(int(user_id), contract_id)
                logger.info(f"Payment processed for user {user_id}")
            else:
                # Если user_id не передан, логируем для ручной обработки
                logger.warning(f"Payment received but no user_id. Email: {buyer_email}, Contract: {contract_id}")
                # Можно добавить поиск по email в базе
        
        return web.Response(status=200, text="OK")
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500, text=str(e))
 
async def handle_health(request: web.Request) -> web.Response:
    """Health check для Railway"""
    return web.Response(status=200, text="OK")
 
async def start_webhook_server():
    """Запуск веб-сервера"""
    app = web.Application()
    app.router.add_post("/webhook/lava", handle_lava_webhook)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Railway даёт порт через переменную окружения
    import os
    port = int(os.environ.get("PORT", 8080))
    
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    logger.info(f"Webhook server started on port {port}")
    return runner
 
async def main():
    """Запуск бота + веб-сервера"""
    await init_db()
    
    # Запускаем веб-сервер
    runner = await start_webhook_server()
    
    # Запускаем бота
    from bot import dp
    logger.info("Bot started!")
    
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
 
if __name__ == "__main__":
    asyncio.run(main())
