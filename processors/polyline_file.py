# # Стандартная библиотека
# import io
# import os
# import statistics
# 
# # Сторонние пакеты
# import folium
# import polyline
# from PIL import Image
# from selenium import webdriver
# from selenium.webdriver.firefox.options import Options
# from selenium.webdriver.firefox.service import Service
# from webdriver_manager.firefox import GeckoDriverManager
# 
# # Настройка Selenium
# options = Options()
# options.add_argument('--headless')
# options.add_argument('--no-sandbox')
# options.add_argument('--disable-dev-shm-usage')
# options.add_argument('--disable-gpu')
# options.binary_location = '/usr/bin/firefox-esr'
# 
# try:
#     service = Service(GeckoDriverManager().install())
#     driver = webdriver.Firefox(
#         options=options,
#         service=service
#     )
# except Exception as e:
#     print(f"Error initializing Firefox driver: {e}")
#     driver = None
# 
# def ensure_media_dir_exists():
#     """Создание директории media, если она не существует"""
#     if not os.path.exists('media'):
#         os.makedirs('media')
# 
# def get_picture(polyline_str: str):
#     """
#     Создание карты тренировки из полилинии
#     
#     Args:
#         polyline_str: Закодированная полилиния маршрута
#     """
#     if driver is None:
#         print("Firefox driver is not initialized, cannot create map")
#         return
# 
#     try:
#         # Декодируем полилинию
#         export_polyline = polyline.decode(polyline_str, 5)
#         
#         if export_polyline:
#             # Извлекаем координаты
#             latitude = []
#             longitude = []
#             for coord in export_polyline:
#                 latitude.append(coord[0])
#                 longitude.append(coord[1])
# 
#             # Вычисляем средние и граничные значения
#             avg_latitude = statistics.mean(latitude)
#             avg_longitude = statistics.mean(longitude)
#             min_latitude = min(latitude)
#             max_latitude = max(latitude)
#             min_longitude = min(longitude)
#             max_longitude = max(longitude)
# 
#             # Создаем карту
#             center_point = [avg_latitude, avg_longitude]
#             m = folium.Map(location=center_point, width=1000, height=1000)
# 
#             # Добавляем маршрут
#             folium.PolyLine(export_polyline).add_to(m)
# 
#             # Настраиваем границы карты
#             delta = 0.00001
#             m.fit_bounds([
#                 (min_latitude + delta, min_longitude + delta),
#                 (max_latitude + delta, max_longitude + delta)
#             ])
# 
#             # Создаем директорию media если нужно
#             ensure_media_dir_exists()
#             
#             # Сохраняем карту как изображение
#             img_data = m._to_png(1)
#             img = Image.open(io.BytesIO(img_data))
#             img.save('media/map.png')
#             print("Saved training map to media/map.png")
#             
#     except Exception as e:
#         print(f"Error creating training map: {e}")

# Закрываем драйвер при завершении работы
import atexit
atexit.register(lambda: driver.quit() if driver else None)
