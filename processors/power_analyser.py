from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

from processors.graph_creater import make_chart
from users import users_data, nl

@dataclass
class PowerZone:
    name: str
    range: Tuple[float, float]
    
    def format_range(self) -> str:
        start = int(self.range[0])
        end = int(self.range[1]) if self.range[1] < 2000 else '∞'
        return f"{self.name}{nl}{start} – {end}"
        
    def contains(self, power: float) -> bool:
        return self.range[0] <= power <= self.range[1]

class PowerAnalyzer:
    def __init__(self, user_id: int):
        self.ftp = int(users_data[str(user_id)]['ftp'])
        self.zones = self._initialize_zones()
        
    def _initialize_zones(self) -> List[PowerZone]:
        """Инициализация зон мощности"""
        zone_configs = [
            ('Восстановление', (0.5, 0.65)),
            ('Выносливость', (0.66, 0.75)),
            ('Темповая', (0.76, 0.92)),
            ('FTP', (0.93, 1.00)),
            ('Анаэробная', (1.01, 2000/self.ftp))  # Преобразуем абсолютное значение в относительное
        ]
        
        return [
            PowerZone(
                name=name,
                range=(self.ftp * start, self.ftp * end)
            )
            for name, (start, end) in zone_configs
        ]
    
    def analyze_power_data(self, power_data: np.ndarray) -> Dict[str, float]:
        """Анализ данных мощности по зонам"""
        if not isinstance(power_data, np.ndarray):
            power_data = np.array(power_data)
            
        # Фильтруем нулевые значения
        valid_power = power_data[power_data > 0]
        total_samples = len(valid_power)
        
        if total_samples == 0:
            return {f'time_in_zone_{i+1}_by_power': 0.0 for i in range(len(self.zones))}
            
        # Вычисляем время в каждой зоне
        zone_times = {}
        for i, zone in enumerate(self.zones, 1):
            time_in_zone = np.sum((valid_power >= zone.range[0]) & (valid_power <= zone.range[1]))
            percentage = round((time_in_zone / total_samples * 100), 1)
            zone_times[f'time_in_zone_{i}_by_power'] = percentage
            
        return zone_times
        
    def create_zone_labels(self) -> Dict[str, str]:
        """Создание меток для зон мощности"""
        return {
            f'zone_{i+1}_by_power': zone.format_range()
            for i, zone in enumerate(self.zones)
        }

def get_power_statistics(power_data: np.ndarray, user_id: int) -> None:
    """
    Анализ статистики мощности и создание графика
    
    Args:
        power_data: Массив данных мощности
        user_id: ID пользователя
    """
    analyzer = PowerAnalyzer(user_id)
    
    # Анализируем данные по зонам
    zone_times = analyzer.analyze_power_data(power_data)
    
    # Создаем метки для зон
    zone_labels = analyzer.create_zone_labels()
    
    # Создаем график
    make_chart(zone_labels, zone_times, 'power')
