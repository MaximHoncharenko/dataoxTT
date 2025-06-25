import asyncio
import os
import sys
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import create_table
from scraper import scrape_autoria
from dump import dump_db

print('sys.argv:', sys.argv)

load_dotenv()

SCRAPING_TIME = os.getenv('SCRAPING_TIME', '12:00')
DUMP_TIME = os.getenv('DUMP_TIME', '12:00')

async def scheduled_main():
    create_table()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scrape_autoria, 'cron', hour=SCRAPING_TIME.split(':')[0], minute=SCRAPING_TIME.split(':')[1])
    scheduler.add_job(dump_db, 'cron', hour=DUMP_TIME.split(':')[0], minute=DUMP_TIME.split(':')[1])
    scheduler.start()
    print('Сервис запущен. Ожидание задач...')
    while True:
        await asyncio.sleep(3600)

async def run_once():
    print('Ручной запуск парсера...')
    create_table()
    await scrape_autoria()
    print('Парсинг завершён.')

def run_dump_now():
    print('Ручной дамп базы...')
    create_table()
    dump_db()
    print('Дамп завершён.')

if __name__ == '__main__':
    if '--run-once' in sys.argv:
        print('Режим: ручной парсинг')
        asyncio.run(run_once())
    elif '--dump-now' in sys.argv:
        print('Режим: ручной дамп')
        run_dump_now()
    else:
        print('Режим: расписание')
        asyncio.run(scheduled_main())
