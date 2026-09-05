# Развёртывание KidsTime

Тестовый контур разворачивается в `/opt/kidstime` пользователем `deploy`. Наружу публикуются только порты 80 и 443 контейнера Caddy. PostgreSQL, Redis и Gunicorn доступны исключительно внутри Docker-сети проекта.

## Переменные окружения

Скопируйте `.env.production.example` в `.env.production` только на сервере. Создайте отдельные случайные значения для `DJANGO_SECRET_KEY` и `POSTGRES_PASSWORD`; пароль PostgreSQL в `DATABASE_URL` должен совпадать с `POSTGRES_PASSWORD`.

Для тестового домена оставьте:

```dotenv
SITE_DOMAIN=kidstime.devtestenv.ru
DJANGO_ALLOWED_HOSTS=kidstime.devtestenv.ru,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://kidstime.devtestenv.ru
ROBOTS_NOINDEX=true
```

`.env.production` не добавляется в Git.

## Проверка конфигурации

```bash
docker compose \
  --env-file .env.production \
  -f compose.production.yaml \
  config --quiet
```

## Запуск

```bash
docker compose \
  --env-file .env.production \
  -f compose.production.yaml \
  up -d --build
```

При первом запуске web-контейнер применяет миграции и, если включено `LOAD_DEMO_DATA=true`, создаёт демонстрационные карточки. Операция идемпотентна.

## Проверка

```bash
docker compose \
  --env-file .env.production \
  -f compose.production.yaml \
  ps

curl -fsS https://kidstime.devtestenv.ru/health/
curl -I https://kidstime.devtestenv.ru/
curl -fsS https://kidstime.devtestenv.ru/robots.txt
```

Для тестового контура ответы должны содержать `X-Robots-Tag: noindex, nofollow, noarchive`, а `robots.txt` — `Disallow: /`.
