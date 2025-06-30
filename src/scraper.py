import asyncio
import aiohttp
from bs4 import BeautifulSoup, Tag
from datetime import datetime
from db import get_conn
import os
from dotenv import load_dotenv
import re
import time

load_dotenv()
START_URL = os.getenv('START_URL')

# Настройки парсера из .env
MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '10'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50'))
REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', '0.2'))
BATCH_DELAY = float(os.getenv('BATCH_DELAY', '2.0'))
MAX_PAGES = int(os.getenv('MAX_PAGES', '1000'))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Семафор для ограничения количества одновременных запросов
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

async def fetch(session, url, max_retries=3):
    """Безопасный fetch с повторными попытками и семафором"""
    async with semaphore:  # Ограничиваем количество одновременных запросов
        for attempt in range(max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=30, connect=10)
                async with session.get(url, headers=HEADERS, timeout=timeout) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    else:
                        print(f"Статус {resp.status} для {url}")
                        if resp.status in [429, 503]:  # Rate limiting или сервер недоступен
                            await asyncio.sleep(5)  # Дольше ждем при лимитах
                        return None
            except (aiohttp.ClientError, asyncio.TimeoutError, aiohttp.ServerDisconnectedError) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Экспоненциальная задержка
                    print(f"Попытка {attempt + 1} не удалась для {url}: {e}. Ждем {wait_time}с")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print(f"Ошибка загрузки {url} после {max_retries} попыток: {e}")
                    return None
        return None

async def fetch_phone(session, car_id, url):
    """Получение телефона несколькими способами с семафором"""
    async with semaphore:  # Ограничиваем одновременные запросы
        try:
            # Способ 1: API для получения телефона
            api_url = f'https://auto.ria.com/users/phones/{car_id}?all'
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(api_url, headers=HEADERS, timeout=timeout) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        if isinstance(data, list) and data:
                            phone = data[0].get('phone')
                            if phone:
                                return re.sub(r'\D', '', phone)
                    except:
                        pass
        except Exception as e:
            print(f"Ошибка получения телефона API1 для {car_id}: {e}")
        
        try:
            # Способ 2: Альтернативный API
            api_url2 = f'https://auto.ria.com/demo/bu/searchPage/v2/view/auto/{car_id}?lang_id=4'
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(api_url2, headers=HEADERS, timeout=timeout) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        phone = data.get('userInfo', {}).get('phone')
                        if phone:
                            return re.sub(r'\D', '', phone)
                    except:
                        pass
        except Exception as e:
            print(f"Ошибка получения телефона API2 для {car_id}: {e}")
        
        return None

def parse_odometer(odometer_str):
    """Преобразует "95 тыс." в 95000"""
    if not odometer_str:
        return None
    odometer_str = odometer_str.replace('тыс.', '000').replace(' ', '').replace('км', '').replace('.', '')
    try:
        return int(odometer_str)
    except Exception:
        return None

def safe_parse_title(soup):
    """Безопасный парсинг заголовка"""
    try:
        selectors = ['h1', '.auto-head_title', '.head-title']
        for selector in selectors:
            title_tag = soup.select_one(selector)
            if title_tag:
                return title_tag.get_text(strip=True)
    except:
        pass
    return None

def safe_parse_price(soup):
    """Безопасный парсинг цены"""
    try:
        selectors = [
            '.price_value', 
            '.price-ticket', 
            '[data-currency="USD"]',
            '.auto-price_value'
        ]
        for selector in selectors:
            price_tag = soup.select_one(selector)
            if price_tag:
                price_text = price_tag.get_text(strip=True)
                price_clean = re.sub(r'[^\d]', '', price_text)
                if price_clean.isdigit():
                    return int(price_clean)
    except:
        pass
    return None

def safe_parse_odometer(soup):
    """Безопасный парсинг пробега"""
    try:
        # Ищем по разным селекторам
        selectors = [
            lambda s: s.find('div', string=lambda t: isinstance(t, str) and 'Пробег' in t),
            lambda s: s.select_one('[data-name="race"]'),
            lambda s: s.select_one('.item_params .race')
        ]
        
        for selector_func in selectors:
            odometer_el = selector_func(soup)
            if odometer_el:
                # Ищем следующий span или в самом элементе
                odometer_text = None
                if hasattr(odometer_el, 'find_next'):
                    next_span = odometer_el.find_next('span')
                    if next_span:
                        odometer_text = next_span.get_text(strip=True)
                if not odometer_text and hasattr(odometer_el, 'get_text'):
                    odometer_text = odometer_el.get_text(strip=True)
                
                if odometer_text:
                    return parse_odometer(odometer_text)
    except:
        pass
    return None

def safe_parse_username(soup):
    """Безопасный парсинг имени продавца"""
    try:
        selectors = [
            '.seller_info_name',
            '.seller-name',
            '[data-name="seller_name"]',
            '.auto-seller_name'
        ]
        for selector in selectors:
            username_tag = soup.select_one(selector)
            if username_tag:
                return username_tag.get_text(strip=True)
    except:
        pass
    return None

def safe_parse_images(soup):
    """Безопасный парсинг изображений"""
    try:
        image_url = None
        images_count = 0
        
        # Селекторы для главного изображения
        img_selectors = [
            '.outline.m-auto',
            '.photo-620x465',
            '.gallery-main img',
            '.auto-photo img'
        ]
        
        for selector in img_selectors:
            image_tag = soup.select_one(selector)
            if image_tag and isinstance(image_tag, Tag):
                src = image_tag.get('src') or image_tag.get('data-src')
                if src:
                    image_url = src
                    break
        
        # Подсчет всех изображений
        all_imgs = soup.select('img[src*="cdn"], img[data-src*="cdn"]')
        images_count = len([img for img in all_imgs if 'photo' in (img.get('src', '') + img.get('data-src', ''))])
        
        return image_url, images_count
    except:
        pass
    return None, 0

def safe_parse_car_details(soup):
    """Безопасный парсинг номера и VIN"""
    try:
        car_number = None
        car_vin = None
        
        # Ищем в разных местах
        detail_selectors = [
            '.item_params .label',
            '.auto-params .label',
            '[data-name="tech_params"] .label'
        ]
        
        for selector in detail_selectors:
            blocks = soup.select(selector)
            for block in blocks:
                if not block:
                    continue
                label_text = block.get_text() if hasattr(block, 'get_text') else ''
                
                if 'Номер кузова' in label_text or 'VIN' in label_text:
                    next_span = block.find_next('span') if hasattr(block, 'find_next') else None
                    if next_span:
                        car_vin = next_span.get_text(strip=True)
                
                if 'Госномер' in label_text or 'номер' in label_text.lower():
                    next_span = block.find_next('span') if hasattr(block, 'find_next') else None
                    if next_span:
                        car_number = next_span.get_text(strip=True)
        
        return car_number, car_vin
    except:
        pass
    return None, None

async def parse_car_page(session, url):
    """Парсинг страницы автомобиля с отдельной обработкой каждого поля"""
    try:
        html = await fetch(session, url)
        if not html:
            print(f"Не удалось загрузить {url}")
            return None
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Безопасный парсинг каждого поля отдельно
        title = safe_parse_title(soup)
        price_usd = safe_parse_price(soup)
        odometer = safe_parse_odometer(soup)
        username = safe_parse_username(soup)
        image_url, images_count = safe_parse_images(soup)
        car_number, car_vin = safe_parse_car_details(soup)
        
        # Получение ID объявления
        car_id = None
        try:
            match = re.search(r'/([0-9]{6,})', url)
            if match:
                car_id = match.group(1)
            if not car_id:
                id_tag = soup.find('div', {'data-id': True})
                if id_tag and isinstance(id_tag, Tag):
                    car_id = id_tag.get('data-id')
        except Exception as e:
            print(f"Ошибка получения car_id из {url}: {e}")
        
        # Получение телефона
        phone_number = None
        if car_id:
            try:
                phone_number = await fetch_phone(session, car_id, url)
            except Exception as e:
                print(f"Ошибка получения телефона для {url}: {e}")
        
        # Дата сохранения
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
        print(f'Критическая ошибка парсинга {url}: {e}')
        return None

async def get_all_car_links(session, start_url):
    """Сбор всех ссылок на автомобили с улучшенной устойчивостью"""
    links = set()
    page = 1
    
    while page <= MAX_PAGES:
        try:
            url = f"{start_url}?page={page}"
            print(f"Парсинг страницы {page}...")
            html = await fetch(session, url)
            
            if not html:
                print(f"Не удалось загрузить страницу {page}")
                break
                
            soup = BeautifulSoup(html, 'lxml')
            
            # Ищем ссылки на авто по разным селекторам
            car_links = []
            
            # Пробуем разные селекторы для ссылок
            selectors = [
                'a.address',
                'a[href*="auto_"]',
                '.item.ticket-title a',
                '.content-bar a[href*="auto"]'
            ]
            
            for selector in selectors:
                found_links = soup.select(selector)
                if found_links:
                    car_links = found_links
                    break
            
            if not car_links:
                print(f"Не найдено ссылок на странице {page}")
                break
            
            new_links_count = 0
            for link in car_links:
                if isinstance(link, Tag):
                    href = link.get('href')
                    if href and isinstance(href, str) and 'auto_' in href:
                        # Делаем абсолютную ссылку
                        if href.startswith('/'):
                            href = 'https://auto.ria.com' + href
                        if href not in links:
                            links.add(href)
                            new_links_count += 1
            
            print(f"Страница {page}: найдено {new_links_count} новых ссылок")
            
            if new_links_count == 0:
                print("Новых ссылок нет, завершаем парсинг страниц")
                break
                
            page += 1
            
            # Небольшая задержка между запросами страниц
            await asyncio.sleep(1.0)
            
        except Exception as e:
            print(f"Ошибка на странице {page}: {e}")
            break
    
    return list(links)

async def save_to_db(car):
    """Сохранение в БД с обработкой ошибок"""
    try:
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
        return True
    except Exception as e:
        print(f"Ошибка сохранения в БД: {e}")
        return False

async def process_batch(session, urls):
    """Обработка батча ссылок"""
    results = []
    for url in urls:
        try:
            car = await parse_car_page(session, url)
            if car:
                if await save_to_db(car):
                    results.append(car)
                    print(f"✓ Сохранено: {car['title'] or 'Без названия'} - {url}")
                else:
                    print(f"✗ Ошибка сохранения: {url}")
            else:
                print(f"✗ Ошибка парсинга: {url}")
        except Exception as e:
            print(f"✗ Ошибка обработки {url}: {e}")
        
        # Небольшая задержка между обработкой каждой ссылки в батче
        await asyncio.sleep(REQUEST_DELAY)
    
    return results

async def scrape_autoria():
    """Основная функция парсинга с батчами для стабильности"""
    print('Старт парсинга AutoRia...')
    
    # Настройки для aiohttp connector
    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENT_REQUESTS,
        limit_per_host=5,  # Максимум 5 соединений к одному хосту
        ttl_dns_cache=300,
        use_dns_cache=True,
        keepalive_timeout=30,
        enable_cleanup_closed=True
    )
    
    timeout = aiohttp.ClientTimeout(total=60, connect=10)
    
    try:
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=HEADERS
        ) as session:
            # Получаем все ссылки
            print("Сбор ссылок на автомобили...")
            links = await get_all_car_links(session, START_URL)
            print(f'Найдено {len(links)} ссылок на авто')
            
            if not links:
                print("Ссылки не найдены. Проверьте селекторы или сайт.")
                return
            
            # Обрабатываем ссылки батчами для стабильности
            batch_size = BATCH_SIZE  # Размер батча из .env
            total_processed = 0
            total_saved = 0
            
            for i in range(0, len(links), batch_size):
                batch = links[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(links) + batch_size - 1) // batch_size
                
                print(f"\n--- Обработка батча {batch_num}/{total_batches} ({len(batch)} ссылок) ---")
                
                try:
                    # Создаем задачи для батча
                    tasks = []
                    for j in range(0, len(batch), MAX_CONCURRENT_REQUESTS):
                        mini_batch = batch[j:j + MAX_CONCURRENT_REQUESTS]
                        tasks.append(process_batch(session, mini_batch))
                    
                    # Выполняем задачи батча
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Подсчитываем результаты
                    for result in batch_results:
                        if isinstance(result, list):
                            total_saved += len(result)
                        elif isinstance(result, Exception):
                            print(f"Ошибка в батче: {result}")
                    
                    total_processed += len(batch)
                    
                    print(f"Батч {batch_num} завершен. Обработано: {total_processed}/{len(links)}, Сохранено: {total_saved}")
                    
                    # Задержка между батчами
                    if i + batch_size < len(links):
                        print("Пауза между батчами...")
                        await asyncio.sleep(BATCH_DELAY)
                        
                except Exception as e:
                    print(f"Ошибка обработки батча {batch_num}: {e}")
                    continue
            
            print(f'\n=== Парсинг завершён ===')
            print(f'Всего обработано: {total_processed} ссылок')
            print(f'Успешно сохранено: {total_saved} автомобилей')
            
    except Exception as e:
        print(f"Критическая ошибка парсера: {e}")
    finally:
        await connector.close()
