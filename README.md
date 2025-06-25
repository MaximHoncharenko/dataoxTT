# AutoRia Scraper

## Описание
Асинхронное приложение для ежедневного сбора данных о б/у авто с AutoRia и сохранения их в PostgreSQL. Дамп базы делается ежедневно в папку `dumps`.

## Требования
- Docker и Docker Compose
- Python (только для локального запуска, не требуется для работы через Docker)

## Структура
- `src/` — исходный код
- `dumps/` — дампы БД
- `.env` — настройки
- `docker-compose.yml` — запуск
- `requirements.txt` — зависимости

## Пример .env
```
START_URL=https://auto.ria.com/uk/car/used/
SCRAPING_TIME=12:00
DUMP_TIME=12:00
POSTGRES_DB=autor_db
POSTGRES_USER=autor_user
POSTGRES_PASSWORD=autor_pass
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

## Запуск
1. Клонируйте репозиторий
2. Заполните `.env` при необходимости
3. Запустите: `docker-compose up --build`

## Ручной запуск парсера и дампа
- Запустить парсер один раз:
  ```
  docker-compose run --rm app python -u src/main.py --run-once
  ```
- Сделать дамп базы вручную:
  ```
  docker-compose run --rm app python -u src/main.py --dump-now
  ```

## Подключение к базе данных
Для подключения к PostgreSQL снаружи используйте:
- host: `localhost`
- port: `5433` (или тот, что указан в docker-compose.yml)
- user: как в `.env`
- password: как в `.env`
- database: как в `.env`

## Настройки
Все настройки в `.env`.

## Дамп БД
Дамп создаётся ежедневно в папке `dumps` и при ручном запуске.
