import asyncio
import aiohttp
from bs4 import BeautifulSoup, Tag
from datetime import datetime
from db import get_conn
import os
from dotenv import load_dotenv
import re

load_dotenv()
START_URL = os.getenv('START_URL')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

async def fetch(session, url):
    async with session.get(url, headers=HEADERS) as resp:
        return await resp.text()

async def fetch_phone(session, car_id):
    # API для получения телефона: https://auto.ria.com/users/phones/{car_id}?all
    api_url = f'https://auto.ria.com/users/phones/{car_id}?all'
    async with session.get(api_url, headers=HEADERS) as resp:
        if resp.status == 200:
            data = await resp.json()
            # Обычно возвращается список номеров
            if isinstance(data, list) and data:
                # Берём первый номер
                phone = data[0].get('phone')
                # Оставляем только цифры
                if phone:
                    return re.sub(r'\D', '', phone)
        return None

def parse_odometer(odometer_str):
    # Преобразует "95 тыс." в 95000
    if not odometer_str:
        return None
    odometer_str = odometer_str.replace('тыс.', '000').replace(' ', '').replace('км', '').replace('.', '')
    try:
        return int(odometer_str)
    except Exception:
        return None

async def parse_car_page(session, url):
    html = await fetch(session, url)
    soup = BeautifulSoup(html, 'lxml')
    try:
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else None
        price_tag = soup.find('span', {'class': 'price_value'})
        price_usd = price_tag.get_text(strip=True).replace('$', '').replace(' ', '') if price_tag else None
        price_usd = int(price_usd) if price_usd and price_usd.isdigit() else None
        odometer_div = soup.find('div', string=lambda t: isinstance(t, str) and 'Пробег' in t)
        odometer = None
        if odometer_div:
            odometer_span = odometer_div.find_next('span')
            odometer = odometer_span.get_text(strip=True) if odometer_span else None
        odometer = parse_odometer(odometer)
        username_tag = soup.find('div', {'class': 'seller_info_name'})
        username = username_tag.get_text(strip=True) if username_tag else None
        # Получаем id объявления из url или из страницы
        car_id = None
        match = re.search(r'/([0-9]{6,})', url)
        if match:
            car_id = match.group(1)
        if not car_id:
            # Пробуем найти в html
            id_tag = soup.find('div', {'data-id': True})
            if id_tag and isinstance(id_tag, Tag):
                car_id = id_tag.get('data-id')
        phone_number = None
        if car_id:
            phone_number = await fetch_phone(session, car_id)
        image_tag = soup.find('img', {'class': 'outline m-auto'})
        image_url = image_tag.get('src') if isinstance(image_tag, Tag) else None
        images_count = len(soup.find_all('img', {'class': 'outline m-auto'}))
        car_number = None
        car_vin = None
        for block in soup.find_all('span', {'class': 'label'}):
            label_text = block.get_text() if block else ''
            if 'Номер кузова' in label_text:
                vin_span = block.find_next('span')
                car_vin = vin_span.get_text(strip=True) if vin_span else None
            if 'Госномер' in label_text:
                num_span = block.find_next('span')
                car_number = num_span.get_text(strip=True) if num_span else None
        datetime_found = datetime.now()
        return {
            'url': url,
            'title': title,
            'price_usd': price_usd,
            'odometer': odometer,
            'username': username,
            'phone_number': phone_number,
            'image_url': image_url,
            'images_count': images_count,
            'car_number': car_number,
            'car_vin': car_vin,
            'datetime_found': datetime_found
        }
    except Exception as e:
        print(f'Ошибка парсинга {url}: {e}')
        return None

async def get_all_car_links(session, start_url):
    links = set()
    page = 1
    while True:
        url = f"{start_url}?page={page}"
        html = await fetch(session, url)
        soup = BeautifulSoup(html, 'lxml')
        car_cards = soup.find_all('a', {'class': 'address'})
        if not car_cards:
            break
        for card in car_cards:
            if isinstance(card, Tag):
                href = card.get('href')
                if href:
                    links.add(href)
        page += 1
    return list(links)

async def save_to_db(car):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO cars (url, title, price_usd, odometer, username, phone_number, image_url, images_count, car_number, car_vin, datetime_found)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            ''', (
                car['url'], car['title'], car['price_usd'], car['odometer'], car['username'],
                car['phone_number'], car['image_url'], car['images_count'], car['car_number'],
                car['car_vin'], car['datetime_found']
            ))
            conn.commit()

async def scrape_autoria():
    print('Старт парсинга AutoRia...')
    async with aiohttp.ClientSession() as session:
        links = await get_all_car_links(session, START_URL)
        print(f'Найдено {len(links)} ссылок на авто')
        tasks = [parse_car_page(session, url) for url in links]
        for future in asyncio.as_completed(tasks):
            car = await future
            if car:
                await save_to_db(car)
    print('Парсинг завершён.')
