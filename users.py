import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

nl = '\n'

first_user = os.getenv('FIRST_USER_ID', '666785382')  # Добавляем значение по умолчанию
second_user = os.getenv('SECOND_USER_ID', '720161048')  # Добавляем значение по умолчанию

def get_user_data(user_id: str) -> Dict[str, Any]:
    """
    Получение данных пользователя с проверкой наличия всех необходимых значений
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Dict[str, Any]: Словарь с данными пользователя
        
    Raises:
        ValueError: Если отсутствуют обязательные значения
    """
    if user_id not in (first_user, second_user):
        raise ValueError(f"Неизвестный ID пользователя: {user_id}")
        
    prefix = 'FIRST_' if user_id == first_user else 'SECOND_'
    
    # Обязательные поля
    required_fields = {
        'client_id': os.getenv(f'{prefix}CLIENT_ID'),
        'client_secret': os.getenv(f'{prefix}CLIENT_SECRET'),
        'user_weight': os.getenv(f'{prefix}USER_WEIGHT'),
        'hr_max': os.getenv(f'{prefix}USER_HRMAX'),
        'threshold': os.getenv(f'{prefix}USER_THRESHOLD'),
        'ftp': os.getenv(f'{prefix}USER_FTP'),
        'weight': os.getenv(f'{prefix}USER_WEIGHT'),
    }
    
    # Необязательные поля
    optional_fields = {
        'athlete_id': os.getenv(f'{prefix}ATHLETE_ID'),
        'access_token': os.getenv(f'{prefix}ACCESS_TOKEN'),
        'refresh_token': os.getenv(f'{prefix}REFRESH_TOKEN'),
    }
    
    # Проверяем наличие обязательных значений
    missing_required = [k for k, v in required_fields.items() if v is None]
    if missing_required:
        raise ValueError(f"Отсутствуют обязательные значения для: {', '.join(missing_required)}")
    
    # Объединяем все поля
    data = {**required_fields, **optional_fields}
    
    # Добавляем ID велосипеда для первого пользователя
    if user_id == first_user:
        data['bike'] = os.getenv('FIRST_USER_BIKE_ID')
        
    return data

users_data = {
    first_user: get_user_data(first_user),
    second_user: get_user_data(second_user)
}
