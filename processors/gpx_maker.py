from dataclasses import dataclass
from typing import List, Optional, Tuple
from statistics import mean

import numpy as np
import requests
from matplotlib import pyplot as plt
from scipy.signal import savgol_filter

from processors.hr_analyser import get_hr_statistics
from processors.power_analyser import get_power_statistics
from main import status_code_checker
from users import users_data

@dataclass
class ActivityData:
    hr_data: np.ndarray
    power_data: np.ndarray

class ActivityDataFetcher:
    BASE_URL = 'https://www.strava.com/api/v3/activities'
    
    def __init__(self, activity_id: int, user_id: int):
        self.activity_id = activity_id
        self.user_id = str(user_id)  # Преобразуем в строку для корректного доступа к users_data
        from main import StravaAPI
        strava_api = StravaAPI()
        if not strava_api.check_and_refresh_token(int(self.user_id)):
            print(f"Failed to refresh token for user {self.user_id}")
        self.token = users_data[self.user_id]['access_token']
        self.session = requests.Session()
        
    def _make_request(self, params: dict) -> List:
        """Выполнение запроса к API с обработкой ошибок"""
        url = f'{self.BASE_URL}/{self.activity_id}/streams'
        headers = {'Authorization': f'Bearer {self.token}'}
        
        try:
            response = self.session.get(url, headers=headers, params=params)
            status_code_checker(response.status_code)
            return response.json()
        except Exception as e:
            print(f"Error making request: {str(e)}")
            return []
            
    def get_activity_data(self) -> Optional[ActivityData]:
        """Получение данных об активности"""
        try:
            hr_data = self._make_request({'keys': 'heartrate'})
            power_data = self._make_request({'keys': 'watts'})
            
            return self._process_data(hr_data, power_data)
        except Exception as e:
            print(f"Error getting activity data: {str(e)}")
            return None
            
    def _process_data(self, hr_response: List, power_response: List) -> ActivityData:
        """Обработка полученных данных"""
        hr_array = np.array([])
        power_array = np.array([])
        
        # Обработка данных пульса
        for stream in hr_response:
            if stream['type'] == 'heartrate':
                data = [x for x in stream['data'] if x is not None and x != 0]
                hr_array = np.array(data)
                break
                
        # Обработка данных мощности
        for stream in power_response:
            if stream['type'] == 'watts':
                data = [x for x in stream['data'] if x is not None and x != 0]
                power_array = np.array(data)
                break
                
        return ActivityData(hr_array, power_array)

def analyze_activity_data(activity_id: int, user_id: int) -> Optional[float]:
    """Анализ данных активности"""
    fetcher = ActivityDataFetcher(activity_id, user_id)
    activity_data = fetcher.get_activity_data()
    
    if not activity_data:
        return None
        
    return process_activity_data(activity_data, user_id)

def process_activity_data(data: ActivityData, user_id: int) -> Optional[float]:
    """Обработка данных активности"""
    if data.hr_data.size > 0 and data.power_data.size > 0:
        get_hr_statistics(data.hr_data, user_id)
        get_power_statistics(data.power_data, user_id)
        return calculate_power_hr_ratio(data)
    
    if data.power_data.size > 0:
        get_power_statistics(data.power_data, user_id)
    if data.hr_data.size > 0:
        get_hr_statistics(data.hr_data, user_id)
    
    return None

def split_data(data: np.ndarray) -> Tuple[List, List]:
    """
    Разделение данных на две части
    
    Args:
        data: Массив данных для разделения
        
    Returns:
        Tuple[List, List]: Две части массива данных
    """
    middle = len(data) // 2
    return data[:middle].tolist(), data[middle:].tolist()

def calculate_power_hr_ratio(data: ActivityData) -> float:
    """
    Расчет соотношения мощности к пульсу
    
    Args:
        data: Данные активности с массивами пульса и мощности
        
    Returns:
        float: Процентное изменение соотношения мощности к пульсу
    """
    try:
        # Определяем минимальную длину массивов
        min_length = min(len(data.hr_data), len(data.power_data))
        
        # Обрезаем массивы до одинаковой длины
        hr_data = data.hr_data[:min_length]
        power_data = data.power_data[:min_length]
        
        # Разделяем данные на две части
        hr_halves = split_data(hr_data)
        power_halves = split_data(power_data)
        
        # Вычисляем средние значения и соотношения
        first_ratio = mean(power_halves[0]) / mean(hr_halves[0])
        second_ratio = mean(power_halves[1]) / mean(hr_halves[1])
        
        # Вычисляем процентное изменение
        return (first_ratio - second_ratio) / first_ratio * 100
    except Exception as e:
        print(f"Error calculating power/hr ratio: {e}")
        return 0.0

def create_power_hr_graph(data: ActivityData, output_path: str = 'media/graph.png'):
    """Создание графика мощности и пульса"""
    try:
        # Определяем минимальную длину массивов
        min_length = min(len(data.hr_data), len(data.power_data))
        
        # Обрезаем массивы до одинаковой длины
        hr_data = data.hr_data[:min_length]
        power_data = data.power_data[:min_length]
        
        fig, ax = plt.subplots(figsize=(12, 12))
        x = range(min_length)
        
        # График пульса
        plt.plot(x, hr_data, color='red', label='Heart Rate')
        
        # График мощности (сглаженный)
        window_length = min(51, min_length - (1 if min_length % 2 == 0 else 0))  # Убедимся, что окно меньше длины данных
        if window_length > 3:  # savgol_filter требует window_length > degree
            smoothed_power = savgol_filter(power_data, window_length, 3)
        else:
            smoothed_power = power_data
            
        plt.plot(x, smoothed_power, color='green', label='Power')
        
        plt.legend()
        plt.grid(True)
        plt.xlabel('Time')
        plt.ylabel('Value')
        plt.title('Heart Rate and Power Over Time')
        
        plt.savefig(output_path, dpi=100)
        print(f"Saved power/hr graph to {output_path}")
    except Exception as e:
        print(f"Error creating power/hr graph: {e}")
    finally:
        plt.close('all')  # Закрываем все фигуры для освобождения памяти

# Для обратной совместимости
def get_initial_data(activity_id: int, user_id: int) -> Optional[float]:
    """Получение и анализ данных активности"""
    return analyze_activity_data(activity_id, user_id)
