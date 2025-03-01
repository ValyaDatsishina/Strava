import os
from datetime import timedelta
from typing import Dict, List, Any

from matplotlib import pyplot as plt
import matplotlib
from scipy.ndimage import gaussian_filter1d

from users import nl

matplotlib.use('agg')

MEDIA_DIR = 'media'

# Настройки шрифтов
FONT_AXES = {'fontsize': 24, 'fontstyle': 'normal'}
FONT_TITLE = {'fontsize': 30, 'fontstyle': 'normal'}

def ensure_media_dir_exists():
    """Создание папки для медиафайлов, если она не существует"""
    if not os.path.exists(MEDIA_DIR):
        os.makedirs(MEDIA_DIR)
        print(f"Created media directory at {os.path.abspath(MEDIA_DIR)}")

def make_chart(list_of_zone: Dict[str, str], dicts_of_zones: Dict[str, float], option: str) -> None:
    """
    Создание графика зон
    
    Args:
        list_of_zone: Словарь с названиями зон
        dicts_of_zones: Словарь с процентами времени в зонах
        option: Тип графика ('hr' или 'power')
    """
    ensure_media_dir_exists()
    
    type_of_measurement = {
        'hr': 'ЧСС, уд/мин',
        'power': 'Мощность, Вт'
    }

    type_of_graph = {
        'power': 'мощности',
        'hr': 'пульса'
    }

    fig, ax = plt.subplots(figsize=(12, 12))

    zones = list(list_of_zone.values())
    percents = list(dicts_of_zones.values())

    bar_labels = [f'{percent}%' for percent in percents]
    bar_colors = ['tab:gray', 'tab:blue', 'tab:green', 'tab:orange', 'tab:red']

    try:
        ax.bar(zones, percents, label=bar_labels, color=bar_colors, width=0.9)
        
        ax.set_ylabel('%', fontdict=FONT_AXES)
        ax.set_xlabel(type_of_measurement[option], fontdict=FONT_AXES)
        ax.legend(title='Разбивка по зонам')
        
        plt.title(f'Распределение по зонам {type_of_graph[option]}{nl}', fontdict=FONT_TITLE)
        
        output_path = os.path.join(MEDIA_DIR, f'graph_by_{option}.png')
        plt.savefig(output_path, facecolor='white', edgecolor='black', dpi=100)
        print(f"Saved chart to {output_path}")
        
    except Exception as e:
        print(f"Error creating chart: {e}")
    finally:
        plt.close(fig)

def create_graph_by_data(
    dates: List[Any],
    values: List[float],
    sigma: int,
    title: str,
    filename: str,
    metrics: str = 'Период всех тренировок'
) -> None:
    """
    Создание графика по данным
    
    Args:
        dates: Список дат
        values: Список значений
        sigma: Параметр сглаживания
        title: Заголовок графика
        filename: Путь для сохранения файла
        metrics: Метрика для оси Y
    """
    ensure_media_dir_exists()
    
    fig, ax = plt.subplots(figsize=(12, 12))
    
    try:
        y_values = gaussian_filter1d(values, sigma=sigma)
        plt.plot(dates, y_values, color='red', linewidth=2)
        
        ax.set_ylabel(nl + metrics, fontdict=FONT_AXES)
        ax.set_xlabel(f'{nl}Период всех тренировок', fontdict=FONT_AXES)
        plt.title(title + nl, fontdict=FONT_TITLE)
        
        plt.savefig(filename, dpi=100)
        print(f"Saved graph to {filename}")
        
    except Exception as e:
        print(f"Error creating graph: {e}")
    finally:
        plt.close(fig)
