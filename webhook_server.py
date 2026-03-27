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

def verify_signature(data: bytes, signature: str) -> bool:
    """Проверка подписи вебхука от Lava Top"""
    if not LAVA_SECRET_KEY:
        logger.warning("LAVA_SECRET_KEY not set, skipping signature verification")
        return True
    
    expected = hmac.new(
        LAVA_SECRET_KEY.encode(),
        data,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)

async def handle_lava_webhook(request: web.Request) -> web.Response:
    """Обработчик вебхука от Lava Top"""
    try:
        # Получаем данные
        data = await request.read()
        signature = request.headers.get("X-Lava-Signature", "")
        
        # Проверяем подпись
        if not verify_signature(data, signature):
            logger.warning("Invalid webhook signature")
            return web.Response(status=403, text="Invalid signature")
        
        # Парсим JSON
        payload = json.loads(data)
        logger.info(f"Lava webhook received: {payload}")
        
        # Извлекаем данные
        # Структура зависит от Lava Top API, примерно так:
        event_type = payload.get("event")
        
        if event_type == "payment.success":
            payment_data = payload.get("data", {})
            payment_id = payment_data.get("id")
            
            # user_id передаётся в metadata при создании платежа
            metadata = payment_data.get("metadata", {})
            user_id = metadata.get("user_id")
            
            if user_id:
                await process_lava_payment(int(user_id), payment_id)
                logger.info(f"Payment processed for user {user_id}")
            else:
                logger.error("No user_id in payment metadata")
        
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
