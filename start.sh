#!/bin/bash

# Запуск миграций базы данных
echo "Running database migrations..."
alembic upgrade head

# Запуск бота
echo "Starting bot..."
python -m bot.main


