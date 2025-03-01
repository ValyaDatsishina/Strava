import os
from typing import Union, Dict, List, Optional

import dotenv
import requests
from requests.exceptions import RequestException

from service import check_mileage
from users import users_data, first_user, second_user

def status_code_checker(status_code: int) -> None:
    """
    Проверка статус-кода HTTP-ответа и генерация соответствующего исключения
    
    Args:
        status_code: HTTP статус-код
    
    Raises:
        Exception: Если статус-код указывает на ошибку
    """
    if status_code == 200:
        return
    elif status_code == 401:
        raise Exception('Требуется обновление токена')
    elif status_code == 403:
        raise Exception('VPN не подключен')
    elif status_code == 404:
        raise Exception('Ресурс не найден')
    elif status_code == 429:
        raise Exception('Слишком много запросов')
    elif status_code == 500:
        raise Exception('Ошибка API Strava')
    else:
        raise Exception(f'Неизвестная ошибка: {status_code}')

class StravaAPI:
    BASE_URL = 'https://www.strava.com/api/v3'
    OAUTH_URL = 'https://www.strava.com/oauth/token'
    
    def __init__(self):
        self.session = requests.Session()
    
    def check_and_refresh_token(self, user_id: int) -> bool:
        """
        Проверка и обновление токена доступа
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: True если токен действителен или успешно обновлен, False в противном случае
        """
        try:
            # Пробуем получить данные с текущим токеном
            token = users_data[str(user_id)]['access_token']
            url = f'{self.BASE_URL}/athlete'
            response = self.session.get(url, params={'access_token': token})
            
            if response.status_code == 200:
                print(f"Token is valid for user {user_id}")
                return True
                
            if response.status_code == 401:
                print(f"Token expired for user {user_id}, refreshing...")
                try:
                    new_token = self.get_fresh_api_token(user_id)
                    users_data[str(user_id)]['access_token'] = new_token
                    print(f"Token refreshed successfully for user {user_id}")
                    return True
                except Exception as e:
                    print(f"Failed to refresh token: {str(e)}")
                    return False
                    
            print(f"Unexpected status code: {response.status_code}")
            return False
            
        except Exception as e:
            print(f"Error checking token: {str(e)}")
            return False
    
    def get_fresh_api_token(self, user_id: int) -> str:
        data = {
            'client_id': users_data[str(user_id)]['client_id'],
            'client_secret': users_data[str(user_id)]['client_secret'],
            'refresh_token': users_data[str(user_id)]['refresh_token'],
            'grant_type': 'refresh_token'
        }
        
        try:
            response = self.session.post(self.OAUTH_URL, data=data).json()
            new_access_token = response['access_token']
            env_key = 'FIRST_ACCESS_TOKEN' if str(user_id) == first_user else 'SECOND_ACCESS_TOKEN'
            dotenv.set_key('.env', env_key, new_access_token, quote_mode='never')
            return new_access_token
        except (RequestException, KeyError) as e:
            raise Exception(f"Failed to refresh token: {str(e)}")

    def get_mileage(self, user_id: int) -> list[str]:
        if str(user_id) != first_user:
            return ['Нет данных по статистике оборудования']
            
        if not self.check_and_refresh_token(user_id):
            return ['Ошибка авторизации в Strava API']
            
        token = users_data[str(user_id)]['access_token']
        bike_id = os.getenv('FIRST_USER_BIKE_ID')
        url = f'{self.BASE_URL}/gear/{bike_id}'
        
        try:
            data = self._make_request(url, {'access_token': token}, user_id)
            if data:
                name = data['name']
                new_mileage = int(data['converted_distance'])
                return check_mileage(name, new_mileage, user_id)
        except Exception as e:
            return [f"Ошибка при получении данных: {str(e)}"]
            
        return ['Нет данных по статистике оборудования']

    def _make_request(self, url: str, params: dict, user_id: int) -> dict | None:
        """Выполнение запроса к API с обработкой ошибок и обновлением токена"""
        try:
            response = self.session.get(url, params=params)
            if response.status_code == 401:  # Unauthorized - токен истек
                print(f"Token expired for user {user_id}, refreshing...")
                new_token = self.get_fresh_api_token(user_id)
                params['access_token'] = new_token
                response = self.session.get(url, params=params)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error occurred: {e}")
            if e.response.status_code == 401:
                print("Authentication failed even after token refresh")
            return None
        except Exception as e:
            print(f"Error making request: {str(e)}")
            return None

    def get_last_activity(self, user_id: int) -> list | None:
        """
        Получение последней активности
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Optional[List]: Список активностей или None в случае ошибки
        """
        if not self.check_and_refresh_token(user_id):
            print(f"Failed to authenticate user {user_id}")
            return []
            
        url = f'{self.BASE_URL}/athlete/activities'
        token = users_data[str(user_id)]['access_token']
        params = {
            'access_token': token,
            'per_page': 1,
            'page': 1
        }
        
        try:
            print(f"Fetching activities for user {user_id}")
            data = self._make_request(url, params, user_id)
            if not data:
                print(f"No activities found for user {user_id}")
                return []  # Возвращаем пустой список вместо None
            print(f"Successfully fetched {len(data)} activities")
            return data
        except Exception as e:
            print(f"Error getting last activity: {str(e)}")
            return []  # Возвращаем пустой список вместо None

# Создаем глобальный экземпляр API
strava_api = StravaAPI()

# Экспортируем функции для обратной совместимости
get_fresh_api_token = strava_api.get_fresh_api_token
get_mileage = strava_api.get_mileage
get_last_activity = strava_api.get_last_activity
