# Стандартная библиотека
from dataclasses import dataclass
from datetime import datetime
from time import strftime, gmtime
from typing import Optional, Any
import logging

# Локальные модули
from db.training import get_last_training
from processors.gpx_maker import get_initial_data
from processors.stats_graber import get_TSS_diagram, get_progress_diagrams
from users import users_data, nl

# Настройка логирования
logger = logging.getLogger(__name__)

@dataclass
class ActivityTypes:
    BIKE = ['заезд', 'виртуальный заезд', 'ride', 'virtualride']
    RUN = ['забег', 'run']

@dataclass
class ActivityData:
    type: str
    date: datetime
    distance: float
    moving_time: str
    elevation_gain: int
    achievement_count: int
    athlete_count: int
    average_pace: str
    average_speed: float
    max_speed: float
    elev_high: int
    elev_low: int
    heartrate: tuple[int | str, int | str]
    calories: Optional[int]
    index: Optional[float]
    temperature: Optional[int]
    power: Optional[tuple] = None
    cadence: Optional[int] = None
    ratio: Optional[float] = None

class ActivityAnalyzer:
    def __init__(self, training_data: dict[str, Any], user_id: int):
        self.data = training_data
        self.user_id = user_id

    def get_type_of_activity(self) -> str:
        """Определение типа активности"""
        activity_type = str.lower(self.data['sport_type'])
        if activity_type in ActivityTypes.BIKE:
            return 'Велосипед'
        if activity_type in ActivityTypes.RUN:
            return 'Бег'
        return 'Неизвестно 🤷'

    def get_heartrate(self) -> tuple[int | str, int | str]:
        """Получение данных о пульсе"""
        if self.data.get('has_heartrate'):
            return (
                int(self.data['average_heartrate']),
                int(self.data['max_heartrate'])
            )
        return ('Неизвестно', 'Неизвестно')

    def get_power(self) -> tuple:
        """Получение данных о мощности"""
        if self.data.get('device_watts'):
            ftp = int(users_data[str(self.user_id)]['ftp'])
            weighted_watts = int(self.data['weighted_average_watts'])
            avg_watts = int(self.data['average_watts'])
            max_watts = int(self.data['max_watts'])
            user_weight = float(users_data[str(self.user_id)]['weight'])
            
            return (
                weighted_watts,
                round(weighted_watts / user_weight, 2),
                avg_watts,
                max_watts,
                round((weighted_watts ** 2 * self.data['moving_time']) / (ftp ** 2 * 3600) * 100, 1)
            )
        return ('Неизвестно',) * 5

    def get_cadence(self) -> int | str:
        """Получение данных о каденсе"""
        return int(self.data['average_cadence']) if 'average_cadence' in self.data else 'Неизвестно'

    def get_ratio(self, power: tuple, hr: tuple) -> Optional[float]:
        """Расчет соотношения мощности к пульсу"""
        if power[0] != 'Неизвестно' and hr[0] != 'Неизвестно':
            return round(power[0] / hr[0], 2)
        return None

    def get_energy_spent(self) -> Optional[int]:
        """Получение данных о потраченной энергии"""
        return int(self.data['kilojoules']) if 'kilojoules' in self.data else None

    def get_index(self) -> Optional[float]:
        """Получение индекса производительности"""
        index = get_initial_data(self.data['id'], self.user_id)
        return round(index, 2) if index else None

    def get_temperature(self) -> Optional[int]:
        """Получение данных о температуре"""
        return int(self.data['average_temp']) if 'average_temp' in self.data else None

    def analyze(self) -> ActivityData:
        """Анализ данных активности"""
        activity_type = self.get_type_of_activity()
        
        data = ActivityData(
            type=activity_type,
            date=datetime.strptime(self.data['start_date_local'], '%Y-%m-%dT%H:%M:%SZ').date(),
            distance=round(self.data['distance'] / 1000, 2),
            moving_time=strftime("%H:%M:%S", gmtime(self.data['moving_time'])),
            elevation_gain=int(self.data['total_elevation_gain']),
            achievement_count=self.data['achievement_count'],
            athlete_count=self.data['athlete_count'] - 1,
            average_pace=strftime("%M:%S", gmtime((1 / self.data['average_speed'] * 1000))) if self.data['average_speed'] > 0 else "0:00",
            average_speed=round(self.data['average_speed'] * 3.6, 2) if self.data['average_speed'] > 0 else 0,
            max_speed=round(self.data['max_speed'] * 3.6, 2) if self.data['max_speed'] > 0 else 0,
            elev_high=int(self.data['elev_high']),
            elev_low=int(self.data['elev_low']),
            heartrate=self.get_heartrate(),
            calories=self.get_energy_spent(),
            index=self.get_index(),
            temperature=self.get_temperature()
        )
        
        if activity_type == 'Велосипед':
            data.power = self.get_power()
            data.cadence = self.get_cadence()
            data.ratio = self.get_ratio(data.power, data.heartrate)
            
        return data

def format_bike_activity(data: ActivityData) -> str:
    """Форматирование данных велосипедной активности"""
    return (
        f'📅Дата – {data.date}{nl}'
        f'🚴🏼‍Вид тренировки – {data.type}{nl}'
        f'⏰Время тренировки – {data.moving_time}{nl}'
        f'📏Расстояние – {data.distance}км{nl}'
        f'🏔️Набор высоты – {data.elevation_gain}м{nl}'
        f'⬆️Максимальная высота – {data.elev_high}м{nl}'
        f'⬇️Минимальная высота – {data.elev_low}м{nl}'
        f'🎖️Количество наград – {data.achievement_count}{nl}'
        f'👯Количество других атлетов – {data.athlete_count}{nl}'
        f'🌡️Средняя температура  – {data.temperature if data.temperature else "Неизвестно"}{nl}'
        f'🧁Потрачено калорий – {data.calories if data.calories else "Неизвестно"}{nl}'
        f'{nl}'
        f'🫀Средний пульс – {data.heartrate[0]}{nl}'
        f'❤️‍Максимальный пульс – {data.heartrate[1]}{nl}'
        f'💪Средняя мощность – {data.power[2]}{nl}'
        f'🧨‍Макс. мощность – {data.power[3]}{nl}'
        f'🏎Средняя скорость – {data.average_speed}{nl}'
        f'🔝Макс. скорость – {data.max_speed}{nl}️'
        f'🔄Средний каденс – {data.cadence}{nl}'
        f'{nl}'
        f'⚖️Удельная мощность – {data.power[1]}{nl}'
        f'💪🏻Усредненная мощность – {data.power[0]}{nl}'
        f'😰TSS – {data.power[4]}{nl}'
        f'📉Изменение мощность/пульс – {data.index if data.index else "Неизвестно"}{nl}'
        f'📶Мощность/пульс – {data.ratio if data.ratio else "Неизвестно"}{nl}'
    )

def format_run_activity(data: ActivityData) -> str:
    """Форматирование данных беговой активности"""
    return (
        f'📅Дата – {data.date}{nl}'
        f"🏃🏼‍‍Вид тренировки – {data.type}{nl}"
        f"📏Расстояние – {data.distance}км{nl}"
        f"⏰Время тренировки – {data.moving_time}{nl}"
        f"🏔️Набор высоты – {data.elevation_gain}м{nl}"
        f"🎖️Количество наград – {data.achievement_count}{nl}"
        f"👯Количество других атлетов – {data.athlete_count}{nl}"
        f"🏎Средняя темп – {data.average_pace}{nl}"
        f'🫀Средний пульс – {data.heartrate[0]}{nl}'
        f'❤️‍Максимальный пульс – {data.heartrate[1]}{nl}'
        f'⬆️Максимальная высота – {data.elev_high}м{nl}'
        f'⬇️Минимальная высота – {data.elev_low}м{nl}'
        f'🧁Потрачено калорий – {data.calories}{nl}'
    )

def generation_analyse(user_id: int) -> str:
    """
    Генерация анализа тренировки
    
    Args:
        user_id: ID пользователя
    
    Returns:
        str: Текст анализа
    """
    logger.info(f"Получение данных о последней тренировке для пользователя {user_id}")
    training_data = get_last_training(user_id)
    if not training_data:
        logger.warning("Нет данных о последней тренировке")
        return "Нет данных о последней тренировке"

    try:
        training = training_data[0]
        logger.info(f"Анализ тренировки {training['id']}")

        analyzer = ActivityAnalyzer(training, user_id)
        activity_data = analyzer.analyze()

        if activity_data.type == 'Велосипед':
            logger.info("Форматирование данных велосипедной тренировки")
            return format_bike_activity(activity_data)
        elif activity_data.type == 'Бег':
            logger.info("Форматирование данных беговой тренировки")
            return format_run_activity(activity_data)
        else:
            logger.warning(f"Неизвестный тип активности: {activity_data.type}")
            return "Неизвестный тип активности"
    except Exception as e:
        logger.error(f"Ошибка при анализе тренировки: {str(e)}", exc_info=True)
        return f"Произошла ошибка при анализе тренировки: {str(e)}"
