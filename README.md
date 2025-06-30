# AutoRia Scraper

## Описание
Асинхронное приложение для ежедневного сбора данных о б/у авто с AutoRia и сохранения их в PostgreSQL. Дамп базы делается ежедневно в папку `dumps`.

**Возможности:**
- Устойчивый асинхронный парсинг с ограничением нагрузки на сервер
- Сбор всех полей (url, title, price_usd, odometer, username, phone_number, image_url, images_count, car_number, car_vin, datetime_found)
- Автоматическая обработка ошибок сети и повторные попытки
- Батчевая обработка для стабильности
- Контроль дублей в БД
- Настройка через .env файл

## Требования
- Docker и Docker Compose
- Python (только для локального запуска, не требуется для работы через Docker)

## Структура
- `src/` — исходный код
  - `main.py` — точка входа, планировщик
  - `scraper.py` — асинхронный парсер
  - `db.py` — работа с БД
  - `dump.py` — создание дампов
- `dumps/` — дампы БД
- `.env` — настройки
- `docker-compose.yml` — запуск
- `requirements.txt` — зависимости

## Настройки (.env файл)

### Основные настройки
```
# URL для парсинга
START_URL=https://auto.ria.com/uk/car/used/

# Время запуска (формат HH:MM)
SCRAPING_TIME=12:00
DUMP_TIME=12:00

# Настройки БД
POSTGRES_DB=autor_db
POSTGRES_USER=autor_user
POSTGRES_PASSWORD=autor_pass
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

### Настройки производительности парсера
```
# Максимум одновременных запросов (по умолчанию 10)
MAX_CONCURRENT_REQUESTS=10

# Размер батча для обработки (по умолчанию 50)
BATCH_SIZE=50

# Задержка между запросами в секундах (по умолчанию 0.2)
REQUEST_DELAY=0.2

# Задержка между батчами в секундах (по умолчанию 2.0)
BATCH_DELAY=2.0

# Максимум страниц для парсинга (по умолчанию 1000)
MAX_PAGES=1000
```

**Рекомендации по настройке:**
- Для быстрого парсинга: `MAX_CONCURRENT_REQUESTS=15`, `REQUEST_DELAY=0.1`, `BATCH_DELAY=1.0`
- Для бережного парсинга: `MAX_CONCURRENT_REQUESTS=5`, `REQUEST_DELAY=0.5`, `BATCH_DELAY=5.0`
- При ошибках сети: уменьшите `MAX_CONCURRENT_REQUESTS` и увеличьте задержки

## Запуск
1. Клонируйте репозиторий
2. Скопируйте `.env.example` в `.env` и настройте при необходимости
3. Запустите: `docker-compose up --build`

## Ручной запуск парсера и дампа
- Запустить парсер один раз:
  ```bash
  docker-compose run --rm app python -u src/main.py --run-once
  ```
- Сделать дамп базы вручную:
  ```bash
  docker-compose run --rm app python -u src/main.py --dump-now
  ```

## Мониторинг
При запуске парсера вы увидите:
- Прогресс сбора ссылок по страницам
- Количество обработанных и сохраненных автомобилей
- Информацию об ошибках и повторных попытках
- Статистику по батчам

## Подключение к базе данных
Для подключения к PostgreSQL снаружи используйте:
- **host:** `localhost`
- **port:** `5433` (или тот, что указан в docker-compose.yml)
- **user:** как в `.env`
- **password:** как в `.env`
- **database:** как в `.env`

### Подключение через psql:
```bash
docker exec -it dataoxtt_db_1 psql -U autor_user -d autor_db
```

### Просмотр данных:
```sql
-- Количество записей
SELECT COUNT(*) FROM cars;

-- Последние добавленные автомобили
SELECT title, price_usd, url, datetime_found 
FROM cars 
ORDER BY datetime_found DESC 
LIMIT 10;
```

## Устранение проблем

### Ошибки сети
Если возникают ошибки типа "ServerDisconnectedError" или "ClientConnectorError":
1. Уменьшите `MAX_CONCURRENT_REQUESTS` до 5-8
2. Увеличьте `REQUEST_DELAY` до 0.5-1.0
3. Увеличьте `BATCH_DELAY` до 5.0

### Медленный парсинг
Для ускорения:
1. Увеличьте `MAX_CONCURRENT_REQUESTS` до 15-20
2. Уменьшите `REQUEST_DELAY` до 0.1
3. Увеличьте `BATCH_SIZE` до 100

### Проблемы с БД
```bash
# Перезапуск только БД
docker-compose restart db

# Просмотр логов БД
docker-compose logs db
```

## Дамп БД
Дамп создаётся ежедневно в папке `dumps` в формате `autor_db_YYYY-MM-DD_HH-MM-SS.sql` и при ручном запуске.
