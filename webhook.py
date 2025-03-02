from fastapi import FastAPI, Request, Response
from typing import Optional
import logging
from telegram import StravaBot
from processors.stats_graber import StravaStatsAnalyzer
from users import users_data

logger = logging.getLogger(__name__)

# Инициализируем бота при старте FastAPI приложения
strava_bot = StravaBot()

app = FastAPI()

@app.get("/webhook")
async def webhook_challenge(request: Request):
    """
    Обработчик для подтверждения подписки на webhook.
    Strava отправляет GET запрос с hub.challenge, который нужно вернуть обратно.
    """
    params = dict(request.query_params)
    hub_mode = params.get("hub.mode")
    hub_challenge = params.get("hub.challenge")
    hub_verify_token = params.get("hub.verify_token")
    
    logger.info(f"Получен запрос на подтверждение webhook: {hub_mode=}, {hub_challenge=}, {hub_verify_token=}")
    
    if hub_mode == "subscribe":
        return {"hub.challenge": hub_challenge}
    return Response(status_code=400)

@app.post("/webhook")
async def webhook_event(request: Request):
    """
    Обработчик webhook событий от Strava.
    Получает уведомления о создании новых тренировок.
    """
    try:
        payload = await request.json()
        logger.info(f"Получено webhook событие: {payload}")
        
        # Проверяем, что это создание новой тренировки
        if (payload.get("object_type") == "activity" and 
            payload.get("aspect_type") in ("create", "update")):
            
            owner_id = payload.get("owner_id")
            
            # Находим Telegram ID пользователя
            for telegram_id, data in users_data.items():
                if str(data.get("athlete_id")) == str(owner_id):
                    # Получаем данные о тренировке через существующую функцию
                    training_data = await strava_bot.async_get_training_data(int(telegram_id))
                    if training_data:
                        # Отправляем уведомление в Telegram
                        strava_bot.bot.send_message(telegram_id, training_data)
                    break
        
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Ошибка при обработке webhook события: {e}")
        return Response(status_code=500) 