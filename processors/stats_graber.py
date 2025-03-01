from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Any
import logging
from functools import lru_cache

import requests
from requests.exceptions import RequestException

from db.training import post_many_training
from db.mongo import db_connect
from processors.graph_creater import create_graph_by_data
from users import users_data

logger = logging.getLogger(__name__)

@dataclass
class ActivityTypes:
    BIKE = ['VirtualRide', 'Ride']
    RUN = ['Run', 'TrailRun']

@dataclass
class TrainingStats:
    week_time: str
    month_time: str
    year_time: str
    total_time: str
    week_tss: float
    six_weeks_tss: float
    tbs: float

class StravaStatsAnalyzer:
    BASE_URL = 'https://www.strava.com/api/v3/athlete/activities'
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.session = requests.Session()
        
    def get_list_of_training(self, limit: Optional[int] = None) -> list[dict]:
        """Получение списка тренировок с API Strava"""
        token = users_data[str(self.user_id)]['access_token']
        params = {
            'access_token': token,
            'per_page': min(limit, 200) if limit else 200,
            'page': 1
        }
        
        trainings = []
        try:
            while True:
                response = self.session.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
                
                if not data or (limit and len(trainings) >= limit):
                    break
                    
                trainings.extend(data[:limit - len(trainings)] if limit else data)
                params['page'] += 1
                
        except RequestException as e:
            logger.error(f"Error fetching training data: {e}")
            return []
            
        if trainings:
            post_many_training(trainings, self.user_id)
        return trainings

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Парсинг даты из строки"""
        return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ').date()

    @staticmethod
    def _get_power(activity: dict) -> Optional[int]:
        """Получение данных о мощности"""
        return activity.get('weighted_average_watts') if activity.get('device_watts') else None

    @staticmethod
    def _get_heartrate(activity: dict) -> Optional[float]:
        """Получение данных о пульсе"""
        return activity.get('average_heartrate')

    @staticmethod
    def _get_pace(activity: dict) -> Optional[float]:
        """Расчет темпа"""
        moving_time = activity.get('moving_time', 0)
        distance = activity.get('distance', 0)
        
        if moving_time > 0 and distance > 0:
            return moving_time / distance * 1000
        return None

    def _calc_tss(self, power: int, moving_time: int) -> float:
        """Расчет TSS (Training Stress Score)"""
        ftp = int(users_data[str(self.user_id)]['ftp'])
        return round((power ** 2 * moving_time) / (ftp ** 2 * 3600) * 100, 1)

    def analyze_training_stats(self) -> TrainingStats:
        """Анализ статистики тренировок"""
        data = list(db_connect(self.user_id, param='training').find({}))
        all_trainings = self.get_list_of_training()
        
        if not data or len(data) < len(all_trainings):
            self.get_full_stats()
            data = list(db_connect(self.user_id, param='training').find({}))
            
        today = datetime.now().date()
        time_periods = {
            'week': timedelta(days=7),
            'month': timedelta(days=31),
            'six_weeks': timedelta(days=42),
            'year': timedelta(days=365)
        }
        
        stats = {
            'week_seconds': 0,
            'month_seconds': 0,
            'year_seconds': 0,
            'total_seconds': 0,
            'week_tss': 0,
            'six_weeks_tss': 0
        }
        
        for activity in data:
            activity_date = self._parse_date(activity['start_date_local'])
            days_diff = today - activity_date
            
            # Обновляем время для всех периодов
            if days_diff <= time_periods['week']:
                stats['week_seconds'] += activity['moving_time']
                if power := self._get_power(activity):
                    stats['week_tss'] += self._calc_tss(power, activity['moving_time'])
                    
            if days_diff <= time_periods['month']:
                stats['month_seconds'] += activity['moving_time']
                
            if days_diff <= time_periods['six_weeks']:
                if power := self._get_power(activity):
                    stats['six_weeks_tss'] += self._calc_tss(power, activity['moving_time'])
                    
            if days_diff <= time_periods['year']:
                stats['year_seconds'] += activity['moving_time']
                
            stats['total_seconds'] += activity['moving_time']
            
        # Расчет средних значений TSS
        avg_week_tss = round(stats['week_tss'] / 7, 2)
        avg_six_weeks_tss = round(stats['six_weeks_tss'] / 42, 2)
        tbs = round(avg_six_weeks_tss - avg_week_tss, 2)
        
        return TrainingStats(
            week_time=str(timedelta(seconds=stats['week_seconds'])),
            month_time=str(timedelta(seconds=stats['month_seconds'])),
            year_time=str(timedelta(seconds=stats['year_seconds'])),
            total_time=str(timedelta(seconds=stats['total_seconds'])),
            week_tss=avg_week_tss,
            six_weeks_tss=avg_six_weeks_tss,
            tbs=tbs
        )

    def get_full_stats(self) -> str:
        """Получение полной статистики"""
        trainings = self.get_list_of_training()
        return post_many_training(trainings, self.user_id)

    def create_tss_diagram(self):
        """Создание диаграммы TSS"""
        trainings = self.get_list_of_training()
        dates = []
        tss_values = []
        
        for training in trainings:
            if training['sport_type'] in ActivityTypes.BIKE:
                if power := self._get_power(training):
                    dates.append(self._parse_date(training['start_date_local']))
                    tss_values.append(self._calc_tss(power, training['moving_time']))
                    
        if tss_values:
            create_graph_by_data(
                dates, 
                tss_values, 
                3, 
                'График TSS за все тренировки', 
                'media/graph_by_TSS.png'
            )

    def create_progress_diagrams(self):
        """Создание диаграмм прогресса"""
        trainings = self.get_list_of_training()
        power_data = {'dates': [], 'ratios': []}
        
        for training in trainings:
            if training['sport_type'] in ActivityTypes.BIKE:
                if (power := self._get_power(training)) and (hr := self._get_heartrate(training)):
                    power_data['dates'].append(self._parse_date(training['start_date_local']))
                    power_data['ratios'].append(round(power / hr, 2))
        
        if power_data['ratios']:
            create_graph_by_data(
                power_data['dates'],
                power_data['ratios'],
                3,
                'Отношение мощности к пульсу',
                'media/graph_power_by_hr.png',
                'Вт/удары в минуту'
            )

def get_stats(user_id: int) -> list[Any]:
    """Получение статистики тренировок"""
    analyzer = StravaStatsAnalyzer(user_id)
    stats = analyzer.analyze_training_stats()
    return [
        stats.week_time,
        stats.month_time,
        stats.year_time,
        stats.total_time,
        stats.week_tss if stats.week_tss else 'Неизвестно',
        stats.six_weeks_tss if stats.six_weeks_tss else 'Неизвестно',
        stats.tbs if stats.tbs else 'Неизвестно'
    ]

def get_full_stats(user_id: int) -> str:
    """Получение полной статистики"""
    analyzer = StravaStatsAnalyzer(user_id)
    return analyzer.get_full_stats()

def delete_all(user_id: int):
    """Удаление всех данных"""
    db_connect(user_id, param='delete_all')

def get_TSS_diagram(user_id: int):
    """Создание диаграммы TSS"""
    analyzer = StravaStatsAnalyzer(user_id)
    analyzer.create_tss_diagram()

def get_progress_diagrams(user_id: int):
    """Создание диаграмм прогресса"""
    analyzer = StravaStatsAnalyzer(user_id)
    analyzer.create_progress_diagrams()
