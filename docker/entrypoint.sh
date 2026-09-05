#!/usr/bin/env sh
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "MODE=APPLY"
    echo "Применяются миграции базы данных KidsTime"
    python manage.py migrate --noinput
fi

if [ "${LOAD_DEMO_DATA:-false}" = "true" ]; then
    echo "MODE=APPLY"
    echo "Создаются или обновляются демонстрационные карточки KidsTime"
    python manage.py seed_demo
fi

exec "$@"
