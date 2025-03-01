from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

from processors.graph_creater import make_chart
from users import users_data, nl

@dataclass
class HeartRateZone:
    name: str
    range: Tuple[float, float]
    
    def format_range(self) -> str:
        start = int(self.range[0])
        end = int(self.range[1]) if self.range[1] < 200 else '∞'
        return f"{self.name}{nl}{start} – {end}"
        
    def contains(self, hr: float) -> bool:
        return self.range[0] <= hr <= self.range[1]

class HeartRateAnalyzer:
    def __init__(self, user_id: int):
        self.threshold = int(users_data[str(user_id)]['threshold'])
        self.hr_max = int(users_data[str(user_id)]['hr_max'])
        self.zones = self._initialize_zones()
        
    def _initialize_zones(self) -> List[HeartRateZone]:
        """Инициализация зон пульса"""
        zone_configs = [
            ('Восстановление', (0.60, 0.75)),
            ('Выносливость', (0.76, 0.84)),
            ('Темповая', (0.85, 0.94)),
            ('ПАНО', (0.95, 1.01)),
            ('VO2 Max', (1.02, self.hr_max/self.threshold))
        ]
        
        return [
            HeartRateZone(
                name=name,
                range=(self.threshold * start, min(self.threshold * end, self.hr_max))
            )
            for name, (start, end) in zone_configs
        ]
    
    def analyze_hr_data(self, hr_data: np.ndarray) -> Dict[str, float]:
        """Анализ данных пульса по зонам"""
        if not isinstance(hr_data, np.ndarray):
            hr_data = np.array(hr_data)
            
        # Фильтруем нулевые и невалидные значения
        valid_hr = hr_data[(hr_data > 0) & (hr_data <= self.hr_max)]
        total_samples = len(valid_hr)
        
        if total_samples == 0:
            return {f'time_in_zone_{i+1}_by_hr': 0.0 for i in range(len(self.zones))}
            
        # Вычисляем время в каждой зоне
        zone_times = {}
        for i, zone in enumerate(self.zones, 1):
            time_in_zone = np.sum((valid_hr >= zone.range[0]) & (valid_hr <= zone.range[1]))
            percentage = round((time_in_zone / total_samples * 100), 1)
            zone_times[f'time_in_zone_{i}_by_hr'] = percentage
            
        return zone_times
        
    def create_zone_labels(self) -> Dict[str, str]:
        """Создание меток для зон пульса"""
        return {
            f'zone_{i+1}_by_hr': zone.format_range()
            for i, zone in enumerate(self.zones)
        }

def get_hr_statistics(hr_data: np.ndarray, user_id: int) -> None:
    """
    Анализ статистики пульса и создание графика
    
    Args:
        hr_data: Массив данных пульса
        user_id: ID пользователя
    """
    analyzer = HeartRateAnalyzer(user_id)
    
    # Анализируем данные по зонам
    zone_times = analyzer.analyze_hr_data(hr_data)
    
    # Создаем метки для зон
    zone_labels = analyzer.create_zone_labels()
    
    # Создаем график
    make_chart(zone_labels, zone_times, 'hr')
