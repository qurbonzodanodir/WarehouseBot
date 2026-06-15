#!/bin/bash
# Автоматический бэкап PostgreSQL базы данных в Telegram
# Скрипт запускается на хост-сервере.

set -e

# Переходим в директорию проекта (определяется динамически относительно расположения скрипта)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

# Загружаем переменные окружения из .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Проверяем наличие токена
if [ -z "${BOT_TOKEN}" ]; then
    echo "Ошибка: Переменная BOT_TOKEN не определена в файле .env!"
    exit 1
fi

# Создаем папку для бэкапов на хосте, если ее нет
BACKUP_DIR="backups"
mkdir -p "${BACKUP_DIR}"

# Имя файлов бэкапа
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
DUMP_FILE="${BACKUP_DIR}/backup_${DATE}.sql"
GZ_FILE="${DUMP_FILE}.gz"

echo "[$(date)] Начало создания бэкапа..."

# 1. Создаем дамп базы данных из контейнера
docker exec warehouse_db pg_dump -U postgres warehouse > "${DUMP_FILE}"

# 2. Сжимаем дамп
gzip -f "${DUMP_FILE}"

echo "[$(date)] Дамп создан и сжат: ${GZ_FILE} (Размер: $(du -sh ${GZ_FILE} | cut -f1))"

# 3. Копируем архив в контейнер приложения
docker cp "${GZ_FILE}" warehouse_backend:/tmp/backup.sql.gz

# 4. Запускаем загрузчик внутри контейнера приложения
echo "[$(date)] Запуск отправки в Telegram..."
docker exec \
  -e TELEGRAM_BOT_TOKEN="${BOT_TOKEN}" \
  -e OWNER_TELEGRAM_ID="${OWNER_TELEGRAM_ID}" \
  -e BACKUP_CHAT_ID="${BACKUP_CHAT_ID}" \
  warehouse_backend \
  python /app/scripts/send_telegram.py /tmp/backup.sql.gz "📦 Резервная копия базы данных от $(date +'%Y-%m-%d %H:%M:%S')"

# 5. Очищаем временный файл в контейнере
docker exec warehouse_backend rm -f /tmp/backup.sql.gz

# 6. Ротация бэкапов на хосте (удаляем файлы старше 3 дней)
echo "[$(date)] Очистка старых бэкапов..."
find "${BACKUP_DIR}" -name "*.sql.gz" -type f -mtime +3 -delete

echo "[$(date)] Резервное копирование завершено успешно! ✅"
