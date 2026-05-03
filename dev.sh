#!/bin/bash
# Скрипт для перезапуска бэкенда с очисткой порта
echo "Очистка порта 8030..."
lsof -t -i :8030 | xargs kill -9 2>/dev/null || true
sleep 1
echo "Запуск бэкенда..."
/Users/nodir/.local/bin/uv run python main.py
