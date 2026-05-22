# intManager discord bot

### 1 Вариант запустить:

##### Необходимая версия:
- 3.11 и выше

##### Шаги:
- Создаем виртуальную среду: `python -m venv .bot`
- Активируем: `source .bot/bin/activate`
- Устанавливаем зависимости: `pip install -r requirements.txt`
- Создаем файл в директории: `config/.env` и пишем свой `DISCORD_TOKEN=`
- Запускаем: `python3 bot.py`

### 2 Вариант запустить:

##### Необходимо:
- docker.io или docker-compose (по желанию)
- Собираем образ: `docker build -t intneo/dsbotintmanager:1.1.3 .`

##### Шаги:
- После успешной сборки создаем файл в директории: `config/.env` и пишем свой `DISCORD_TOKEN=`
- Создаем директорию: `data`

##### docker compose:
```
docker compose up -d
```

##### docker run:
```
docker run -d \
  --name dsbotintmanager \
  --restart unless-stopped \
  -e ENV_FILE=/app/config/.env \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  intneo/dsbotintmanager:1.1.3
```