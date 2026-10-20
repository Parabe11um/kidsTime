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

Обязательная переменная `CADDY_IMAGE` задаёт точный образ общего прокси.
Используйте значение из `release.env` проверенного комплекта score-it и сначала
загрузите этот образ в локальный Docker. В `.env.production.example` значение
пустое намеренно: Compose остановится, пока образ не выбран. Автоматическое
скачивание отключено через `pull_policy: never`; плавающий `caddy:2-alpine`
больше не используется. Официальный Caddy той же версии не заменяет проверенную
сборку: встроенные Go-зависимости могут различаться.

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
    import private-access-log
    encode zstd gzip
    header >Referrer-Policy no-referrer
    reverse_proxy score-it-web:8000
}
```

Актуальный шаблон находится в `deploy/score-it.caddy.example`. При обновлении
мастер-файла существующий серверный `score-it.caddy` тоже нужно привести к этому
шаблону, сохранив свой домен. Сам `git pull` не изменяет исключённые из Git файлы.

Сниппет `private-access-log` заменяет весь путь и query string на `[redacted]`
и удаляет request/response headers из access log. Та же фильтрация в глобальном
`log default` защищает журнал ошибок прокси, включая 502. Код ответа, домен,
метод и длительность запроса остаются в журнале. Политика `no-referrer` для
score-it не позволяет браузеру передать адрес комнаты следующему сайту.
Префикс `>` применяет заголовок после upstream, даже если приложение вернуло
другую referrer policy.
`debug` и `log_credentials` включать нельзя: произвольные сообщения сторонних
модулей не покрываются фильтрами структурированных полей.

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

При обновлении образа вместо `restart` используйте пересоздание **только Caddy**:

```bash
"${COMPOSE[@]}" run --rm --no-deps --pull never -T \
  --entrypoint caddy caddy validate \
  --config /etc/caddy/Caddyfile --adapter caddyfile </dev/null
"${COMPOSE[@]}" up -d --no-deps --no-build --pull never caddy </dev/null
```

Этот запуск сохраняет сети, mounts и тома сертификатов из production Compose;
web, PostgreSQL и Redis не пересоздаются. Краткий перерыв HTTPS затронет оба сайта.

До переноса образа на сервер проверьте его в отдельном окружении:

```bash
python3 tests/check_caddy_security.py \
  --image "$CADDY_IMAGE" --backend-image "$SCORE_IT_IMAGE"
```

Оба образа должны быть уже загружены из проверенного комплекта. Проверка создаёт
две временные внутренние сети и три контейнера с уникальными именами, выполняет
запросы внутри Docker без публикации портов и удаляет свои ресурсы после завершения.
Она проверяет HTTP-маршруты обоих upstream, media KidsTime, referrer policy,
отсутствие синтетических токенов в access log и в журнале ошибки 502.
Рабочие приложения и тома сертификатов не используются. CI проверяет конфигурацию
на закреплённом Caddy 2.11.7; перед выкладкой эту же проверку нужно выполнить
на конкретном образе из комплекта. Публичный TLS и сертификаты проверяются
отдельно после применения.

После применения проверьте `https://kidstime.devtestenv.ru/health/` и health
добавленного приложения. Удаление стека KidsTime также останавливает общий
прокси: для независимых жизненных циклов его следует выделить в отдельный стек.
