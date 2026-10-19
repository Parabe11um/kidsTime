# Развёртывание KidsTime

Тестовый контур разворачивается в `/opt/kidstime` пользователем `deploy`. Наружу публикуются только порты 80 и 443 контейнера Caddy. PostgreSQL и Redis доступны внутри Docker-сети проекта. Gunicorn KidsTime остаётся в этой же сети; общий Caddy дополнительно подключён к сети прокси для других приложений.

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

## Общий Caddy для нескольких приложений

Production Compose подключает Caddy к сети проекта и отдельной сети
`score_it_proxy`. Имя второй сети задаётся через `CADDY_PROXY_NETWORK`; сеть
создаёт Compose KidsTime. PostgreSQL, Redis и web KidsTime к этой второй сети
не подключаются. Web KidsTime получает в своей сети уникальный alias
`kidstime-web`; основной маршрут Caddy использует именно его. Общие имена
сервисов вроде `web` могут совпадать у разных приложений, поэтому для upstream
общего прокси используйте уникальные имена.

Другие приложения объявляют эту сеть как `external: true` и подключают к ней
только свой web. Например, score-it использует в ней имя `score-it-web`;
его PostgreSQL остаётся в собственной закрытой сети.

Дополнительные домены хранятся только на сервере в
`deploy/caddy-extra/*.caddy`. Каталог монтируется в Caddy только для чтения;
файлы маршрутов исключены из Git и сохраняются при обычном обновлении репозитория.
Пустой каталог допустим. Пример файла `deploy/caddy-extra/score-it.caddy`:

```caddyfile
score-it.devtestenv.ru {
    encode zstd gzip
    reverse_proxy score-it-web:8000
}
```

Добавляйте HTTPS-маршрут после подготовки приложения и переключения DNS на этот
сервер: получение публичного сертификата требует доступного HTTP/TLS challenge.
До переключения можно подготовить файл с расширением `.disabled`: Caddy его
не импортирует. Не добавляйте файл `.caddy`, который направляет пользователей
в пробную базу.

При первом применении сетевого alias сначала пересоздайте web, затем Caddy:

```bash
COMPOSE=(docker compose --env-file .env.production -f compose.production.yaml)

"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" run --rm --no-deps --pull never -T \
  --entrypoint caddy caddy validate \
  --config /etc/caddy/Caddyfile --adapter caddyfile </dev/null
"${COMPOSE[@]}" up -d --no-deps --no-build --pull never \
  --wait --wait-timeout 120 web </dev/null
"${COMPOSE[@]}" up -d --no-deps --no-build --pull never caddy </dev/null
```

Предварительная проверка не изменяет работающий контейнер, но может создать
сеть и служебные тома проекта. Существующий `admin off` сохранён:
`caddy reload` не работает, поэтому при следующих изменениях маршрутов после
`validate` используйте `"${COMPOSE[@]}" restart caddy </dev/null`.
Во время пересоздания или перезапуска возможен краткий перерыв HTTPS обоих сайтов.
При первом применении пересоздаётся web KidsTime с прежним образом; его entrypoint
может выполнить штатные миграции. PostgreSQL и Redis эти команды не пересоздают.
Последующие изменения маршрутов требуют только перезапуска Caddy.

После применения проверьте `https://kidstime.devtestenv.ru/health/` и health
добавленного приложения. Удаление стека KidsTime также останавливает общий
прокси: для независимых жизненных циклов его следует выделить в отдельный стек.
