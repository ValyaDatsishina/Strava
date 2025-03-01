# Этап сборки
FROM python:3.12-slim AS builder

WORKDIR /app

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Настройка pip для повторных попыток
RUN echo '[global]\n\
timeout = 100\n\
retries = 3\n\
default-timeout = 100' > /etc/pip.conf

# Копируем только requirements.txt
COPY requirements.txt .

# Создаем виртуальное окружение и устанавливаем зависимости с повторными попытками
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt \
    && find /venv -type d -name "__pycache__" -exec rm -r {} + \
    && find /venv -type d -name "*.dist-info" -exec rm -r {} + \
    && find /venv -type d -name "*.egg-info" -exec rm -r {} +

# Финальный этап
FROM python:3.12-slim

WORKDIR /app

# Устанавливаем netcat для проверки соединения
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Создаем директорию для медиафайлов
RUN mkdir -p media && chmod 777 media

# Копируем виртуальное окружение из этапа сборки
COPY --from=builder /venv /venv

# Копируем код приложения
COPY . .

# Используем виртуальное окружение
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Создаем скрипт для запуска
RUN echo '#!/bin/sh\n\
set -ex\n\
\n\
echo "[$(date)] Starting initialization..."\n\
\n\
# Проверяем наличие файла telegram.py\n\
if [ ! -f telegram.py ]; then\n\
    echo "Error: telegram.py not found!"\n\
    exit 1\n\
fi\n\
\n\
# Проверяем наличие переменных окружения\n\
if [ -z "$TELEGRAM_API_TOKEN" ]; then\n\
    echo "Error: TELEGRAM_API_TOKEN is not set!"\n\
    exit 1\n\
fi\n\
\n\
# Проверяем виртуальное окружение\n\
if ! which python >/dev/null; then\n\
    echo "Error: Python not found in PATH!"\n\
    exit 1\n\
fi\n\
\n\
# Проверяем подключение к MongoDB\n\
echo "[$(date)] Checking MongoDB connection..."\n\
MONGO_HOST=$(echo $MONGO_URI | sed -n "s/.*mongodb:\\/\\/\\([^:\\/]*\\).*/\\1/p")\n\
if [ -z "$MONGO_HOST" ]; then\n\
    echo "Warning: Could not parse MongoDB host from MONGO_URI"\n\
    MONGO_HOST="mongo_db"\n\
fi\n\
echo "[$(date)] Waiting for MongoDB at $MONGO_HOST..."\n\
timeout 30 sh -c "until nc -z $MONGO_HOST 27017; do echo .; sleep 1; done" || echo "Warning: MongoDB connection timeout"\n\
\n\
echo "[$(date)] Environment check passed, starting bot..."\n\
\n\
# Создаем тестовый файл для проверки прав записи\n\
if ! touch media/test.txt 2>/dev/null; then\n\
    echo "Error: Cannot write to media directory!"\n\
    exit 1\n\
fi\n\
rm -f media/test.txt\n\
\n\
# Выводим информацию о переменных окружения\n\
echo "[$(date)] Environment variables:"\n\
env | grep -v "TOKEN"\n\
\n\
# Проверяем установленные пакеты Python\n\
echo "[$(date)] Installed Python packages:"\n\
pip list\n\
\n\
# Запускаем бота в отладочном режиме\n\
echo "[$(date)] Starting bot in debug mode..."\n\
PYTHONPATH=/app PYTHONDEVMODE=1 exec python -u -X dev telegram.py 2>&1' > /usr/local/bin/run.sh && chmod +x /usr/local/bin/run.sh

# Запускаем приложение
CMD ["/usr/local/bin/run.sh"]