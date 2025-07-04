FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y postgresql-client
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-u", "src/main.py"]
