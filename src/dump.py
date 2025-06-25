import os
from datetime import datetime
from dotenv import load_dotenv
import subprocess

load_dotenv()

def dump_db():
    db = os.getenv('POSTGRES_DB')
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD') or ''
    host = os.getenv('POSTGRES_HOST')
    port = os.getenv('POSTGRES_PORT')
    dumps_dir = os.path.join(os.path.dirname(__file__), '..', 'dumps')
    os.makedirs(dumps_dir, exist_ok=True)
    filename = f"dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    filepath = os.path.join(dumps_dir, filename)
    print(f'Создание дампа БД: {filepath}')
    # Создаём .pgpass
    home_dir = os.path.expanduser('~')
    pgpass_path = os.path.join(home_dir, '.pgpass')
    with open(pgpass_path, 'w') as f:
        f.write(f"{host}:{port}:{db}:{user}:{password}\n")
    os.chmod(pgpass_path, 0o600)
    cmd = [
        'pg_dump',
        '-h', host,
        '-p', str(port),
        '-U', user,
        '-d', db,
        '-F', 'c',
        '-b',
        '-v',
        '-f', filepath
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f'Ошибка дампа: {e}')
