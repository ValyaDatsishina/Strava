from main import get_last_activity, StravaAPI
from db.mongo import db_connect
import logging

logger = logging.getLogger(__name__)


def post_training(response: list, user_id: int):
    if not response:  # Проверяем, что список не пустой
        return
        
    coll = db_connect(user_id, param='training')
    document = response[0]
    if coll.find_one(filter={'id': document['id']}) is None:
        coll.insert_one(document)


def post_many_training(list_of_all_training: list, user_id: int) -> str:
    if not list_of_all_training:  # Проверяем, что список не пустой
        return "Нет данных для загрузки"
        
    coll = db_connect(user_id, param='training')
    count = len(list_of_all_training)
    for i in range(0, count):
        document = list_of_all_training[i]
        if coll.find_one(filter={'id': document['id']}) is None:
            coll.insert_one(document)

    count_name = correct_count_name(count)
    return f'{count} {count_name}'


def get_last_training(user_id: int):
    """
    Получение данных о последней тренировке
    
    Args:
        user_id: ID пользователя
        
    Returns:
        list: Список с данными о последней тренировке или None, если данные недоступны
    """
    logger.info(f"Получение последней тренировки для пользователя {user_id}")
    
    try:
        # Сначала проверяем в базе данных
        coll = db_connect(user_id, param='training')
        cached_training = list(coll.find().sort("start_date_local", -1).limit(1))
        
        # Получаем последнюю тренировку через API
        strava_api = StravaAPI()
        api_training = strava_api.get_last_activity(user_id)
        
        if not api_training:
            logger.warning("Нет ответа от API Strava")
            return cached_training if cached_training else None
            
        # Если в кэше нет данных или ID тренировок различаются
        if not cached_training or api_training[0]['id'] != cached_training[0]['id']:
            logger.info("Получены новые данные о тренировке")
            if api_training:
                post_training(api_training, user_id)
            return api_training
            
        logger.info("Возвращаем кэшированные данные о тренировке")
        return cached_training
        
    except Exception as e:
        logger.error(f"Ошибка при получении последней тренировки: {str(e)}", exc_info=True)
        return None


def correct_count_name(count: int) -> str:
    if count % 10 in (0, 5, 6, 7, 8, 9):
        return 'тренировок успешно загружено'
    elif count % 10 in (2, 3, 4):
        return 'тренировки успешно загружены'
    else:
        return 'тренировка успешно загружена'
