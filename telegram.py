import glob
import os
import time
import logging
from typing import Optional
from functools import wraps

from dotenv import load_dotenv
from telebot import TeleBot, types
from telebot.types import InputMediaPhoto, Message
from telebot.handler_backends import State, StatesGroup

from db.service_of_bike import cleaning
from processors.json_worker import generation_analyse
from main import get_mileage
from processors.stats_graber import (
    get_stats, 
    get_full_stats, 
    get_TSS_diagram, 
    delete_all, 
    get_progress_diagrams
)
from users import nl

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TELEGRAM_API_TOKEN')

if not TOKEN:
    raise ValueError("Не задан токен бота. Убедитесь, что переменная TELEGRAM_API_TOKEN определена в файле .env")

# Инициализация бота
bot = TeleBot(TOKEN)

class StravaBot:
    MEDIA_DIR = 'media'
    
    def __init__(self):
        self.bot = bot  # Используем глобальный экземпляр бота
        logger.info("Инициализация StravaBot...")
        self.setup_handlers()
        self._ensure_media_dir_exists()
        logger.info("StravaBot успешно инициализирован")
    
    def _ensure_media_dir_exists(self):
        """Создание папки для медиафайлов, если она не существует"""
        if not os.path.exists(self.MEDIA_DIR):
            os.makedirs(self.MEDIA_DIR)
            print(f"Created media directory at {os.path.abspath(self.MEDIA_DIR)}")
    
    def error_handler(func):
        @wraps(func)
        def wrapper(self, message, *args, **kwargs):
            try:
                logger.info(f"Вызов обработчика {func.__name__} для пользователя {message.chat.id}")
                result = func(self, message, *args, **kwargs)
                logger.info(f"Обработчик {func.__name__} успешно выполнен")
                return result
            except Exception as e:
                error_msg = f"Произошла ошибка в {func.__name__}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.bot.reply_to(message, error_msg)
        return wrapper
        
    def cleanup_media(self):
        """Очистка медиафайлов после отправки"""
        if not os.path.exists(self.MEDIA_DIR):
            logger.info(f"Папка {self.MEDIA_DIR} не существует")
            return

        files = glob.glob(f'{self.MEDIA_DIR}/*')
        logger.info(f"Найдено {len(files)} файлов для удаления")

        for f in files:
            try:
                os.remove(f)
                logger.info(f"Удален файл: {f}")
            except OSError as e:
                logger.error(f"Ошибка при удалении файла {f}: {e}")

    def send_media_files(self, chat_id: int, file_paths: list[str]) -> None:
        """Отправка медиафайлов пользователю"""
        logger.info(f"Подготовка медиафайлов для отправки пользователю {chat_id}")
        media = []
        missing_files = []
        
        for path in file_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as photo_file:
                        media.append(InputMediaPhoto(photo_file.read()))
                    logger.info(f"Файл {path} добавлен в группу медиа")
                except Exception as e:
                    logger.error(f"Ошибка при добавлении файла {path}: {e}")
                    missing_files.append(path)
            else:
                logger.warning(f"Файл не найден: {path}")
                missing_files.append(path)
        
        if missing_files:
            logger.warning(f"Не найдены файлы: {', '.join(missing_files)}")
            self.bot.send_message(
                chat_id,
                f"Не удалось найти следующие файлы:\n{nl.join(missing_files)}"
            )
        
        if media:
            try:
                logger.info(f"Отправка {len(media)} файлов пользователю {chat_id}")
                self.bot.send_media_group(chat_id, media, disable_notification=True)
                logger.info("Медиафайлы успешно отправлены")
            except Exception as e:
                logger.error(f"Ошибка при отправке медиафайлов: {e}", exc_info=True)
                self.bot.send_message(
                    chat_id,
                    f"Ошибка при отправке медиафайлов: {str(e)}"
                )
        else:
            logger.warning(f"Нет доступных медиафайлов для отправки пользователю {chat_id}")
            self.bot.send_message(
                chat_id,
                "Нет доступных медиафайлов для отправки"
            )
            
    @error_handler
    def get_training_data(self, message: Message) -> None:
        """Получение данных о последней тренировке"""
        user_id = message.chat.id
        logger.info(f"Запрос данных о последней тренировке от пользователя {user_id}")
        
        self._ensure_media_dir_exists()  # Проверяем наличие папки
        logger.info("Папка для медиафайлов проверена")
        
        text = generation_analyse(user_id)
        logger.info("Анализ тренировки сгенерирован")
        self.bot.send_message(user_id, text=text)

        media_files = [
            f'{self.MEDIA_DIR}/map.png',
            f'{self.MEDIA_DIR}/graph_by_power.png',
            f'{self.MEDIA_DIR}/graph_by_hr.png'
        ]
        logger.info(f"Подготовлен список медиафайлов: {media_files}")
        
        self.send_media_files(user_id, media_files)
        logger.info("Медиафайлы отправлены")
        
        self.cleanup_media()
        logger.info("Медиафайлы очищены")

    @error_handler
    def get_progress(self, message: Message) -> None:
        """Получение данных о прогрессе"""
        user_id = message.chat.id
        self._ensure_media_dir_exists()  # Проверяем наличие папки
        
        get_progress_diagrams(user_id)

        media_files = [
            f'{self.MEDIA_DIR}/graph_power_by_hr.png',
            f'{self.MEDIA_DIR}/graph_pace_by_hr.png'
        ]
        
        self.send_media_files(user_id, media_files)
        self.cleanup_media()

    @error_handler
    def get_statistics(self, message: Message) -> None:
        """Получение статистики"""
        user_id = message.chat.id
        self._ensure_media_dir_exists()  # Проверяем наличие папки
        
        data = get_stats(user_id)
        get_TSS_diagram(user_id)

        if isinstance(data, list):
            stats_text = (
                f'Время тренировок за последние 7 дней:{nl}{data[0]}{nl}{nl}'
                f'Время тренировок за последний 31 день:{nl}{data[1]}{nl}{nl}'
                f'Время тренировок за последние 365 дней:{nl}{data[2]}{nl}{nl}'
                f'Время тренировок за все время:{nl}{data[3]}{nl}{nl}'
                f'TSS за последние 7 дней (ATL): {data[4]}{nl}{nl}'
                f'TSS за последние 6 недель (CTL): {data[5]}{nl}{nl}'
                f'TSB: {data[6]}'
            )
            self.bot.send_message(user_id, text=stats_text)
        else:
            self.bot.send_message(user_id, text=data)

        tss_graph = f'{self.MEDIA_DIR}/graph_by_TSS.png'
        if os.path.exists(tss_graph):
            try:
                with open(tss_graph, 'rb') as photo:
                    self.bot.send_photo(user_id, photo=photo)
            except Exception as e:
                print(f"Error sending TSS graph: {e}")
                self.bot.send_message(
                    user_id,
                    "Ошибка при отправке графика TSS"
                )
        else:
            print(f"TSS graph not found: {tss_graph}")
            self.bot.send_message(
                user_id,
                "График TSS не был создан"
            )
        
        self.cleanup_media()

    @error_handler
    def get_service_info(self, message: Message) -> None:
        """Получение информации об обслуживании"""
        user_id = message.chat.id
        text = get_mileage(user_id)
        self.bot.send_message(user_id, text=text)

    @error_handler
    def get_fully_stat(self, message: Message, param: Optional[str] = None) -> None:
        """Получение полной статистики"""
        user_id = message.chat.id
        
        if param == 'delete':
            delete_all(user_id)
            self.bot.send_message(user_id, text='Данные удалены')
        else:
            text = get_full_stats(user_id)
            self.bot.send_message(user_id, text=text)

    @error_handler
    def service(self, message: Message, param: str) -> None:
        """Обработка сервисных команд"""
        user_id = message.chat.id
        text = cleaning(message, param)
        self.bot.send_message(user_id, text, reply_markup=self.service_keyboard())

    def setup_handlers(self):
        """Настройка обработчиков сообщений"""
        @self.bot.message_handler(commands=['start'])
        def start(message):
            text = f'Привет, {message.chat.first_name}!{nl}Выбери интересующий пункт меню ⬇'
            self.bot.send_message(message.chat.id, text, reply_markup=self.main_keyboard())

        @self.bot.message_handler(content_types=['text'])
        def handle_text(message):
            if message.chat.type == 'private':
                self.process_text_message(message)

    def process_text_message(self, message: Message) -> None:
        """Обработка текстовых сообщений"""
        logger.info(f"Получено сообщение от пользователя {message.chat.id}: {message.text}")
        handlers = {
            'Последняя тренировка': self.get_training_data,
            'Прогресс': self.get_progress,
            'Статистика': self.get_statistics,
            'Пробег': self.get_service_info,
            'Загрузить тренировки': lambda m: self.get_fully_stat(m),
            'Обслуживание': self.show_service_menu,
            'Почистил цепь': lambda m: self.service(m, 'chain'),
            'Почистил привод': lambda m: self.service(m, 'drive'),
            'Последнее обслуживание': lambda m: self.service(m, 'info'),
            'Удалить данные': self.show_confirmation,
            'Да': lambda m: self.get_fully_stat(m, 'delete'),
        }
        
        handler = handlers.get(message.text)
        if handler:
            logger.info(f"Вызов обработчика для команды: {message.text}")
            handler(message)
        else:
            logger.warning(f"Неизвестная команда: {message.text}")
            self.show_main_menu(message)

    def show_service_menu(self, message: Message) -> None:
        """Показать меню обслуживания"""
        self.bot.send_message(
            message.chat.id,
            'Выбери интересующий пункт меню ⬇',
            reply_markup=self.service_keyboard()
        )

    def show_main_menu(self, message: Message) -> None:
        """Показать главное меню"""
        self.bot.send_message(
            message.chat.id,
            'Выбери интересующий пункт меню ⬇',
            reply_markup=self.main_keyboard()
        )

    def show_confirmation(self, message: Message) -> None:
        """Показать меню подтверждения"""
        self.bot.send_message(
            message.chat.id,
            'Уверен?',
            reply_markup=self.confirmation_keyboard()
        )

    @staticmethod
    def main_keyboard() -> types.ReplyKeyboardMarkup:
        """Создание главной клавиатуры"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = [
            'Последняя тренировка', 'Статистика',
            'Загрузить тренировки', 'Прогресс',
            'Обслуживание', 'Удалить данные'
        ]
        markup.add(*buttons)
        return markup

    @staticmethod
    def service_keyboard() -> types.ReplyKeyboardMarkup:
        """Создание клавиатуры обслуживания"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ['Почистил цепь', 'Почистил привод', 
                  'Последнее обслуживание', 'Выход']
        markup.add(*buttons)
        return markup

    @staticmethod
    def confirmation_keyboard() -> types.ReplyKeyboardMarkup:
        """Создание клавиатуры подтверждения"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add('Да', 'Нет')
        return markup

    def run(self):
        """Запуск бота"""
        logger.info("Запуск бота в режиме polling...")
        try:
            logger.info("Настройка обработчиков команд...")
            self.bot.remove_webhook()
            logger.info("Webhook удален, запуск long polling...")
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Критическая ошибка при работе бота: {e}", exc_info=True)
            raise

def run_bot():
    """Запуск бота с автоматическим перезапуском при ошибках"""
    strava_bot = StravaBot()
    while True:
        try:
            logger.info("Инициализация нового экземпляра бота...")
            strava_bot.run()
        except Exception as e:
            logger.error(f"Бот упал с ошибкой: {e}", exc_info=True)
            logger.info("Перезапуск бота через 5 секунд...")
            time.sleep(5)
            continue

if __name__ == '__main__':
    logger.info("Запуск приложения...")
    run_bot()