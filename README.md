# intManager - простой, многофункциональный бот для вашего сервера.

### Инструкция по развертыванию:

##### Необходимо:
- Скачать репозиторий: `git clone https://github.com/intNeo/intmanager.git`
- Должен быть предустановлен `docker` или `docker compose` (по желанию, лучше из официальной документации)

##### Шаги:
- Собираем образ: `docker build -t intneo/dsbotintmanager:1.2.1 .`
- После успешной сборки создаем файл в директории: `config/.env` и пишем свой `DISCORD_TOKEN=`
- Создаем директорию: `data`

##### docker run:
```
docker run -d \
  --name dsbotintmanager \
  --restart unless-stopped \
  -e ENV_FILE=/app/config/.env \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  intneo/dsbotintmanager:1.2.1
```

##### docker compose:
```
docker compose up -d
```