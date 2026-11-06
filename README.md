# Telegram Smetana Utilits (telethon)

Личный Telegram-бот на базе **Telethon** с набором утилит: аналитика чатов, деанон пользователей, ИИ-функции (GPT), конвертация единиц/валют, распознавание голоса, скачивание медиа с YouTube и других хостингов, погода, перевод, сокращение ссылок и другое.

> ⚠️ **Важно:** бот работает от твоего личного аккаунта Telegram. Команды `.deanon`, `.stat`, `.photo` и подобные являются **инструментами для работы с собственными диалогами** и не предназначены для слежки за третьими лицами. Используй ответственно и в рамках законодательства.

---

## 🚀 Возможности

### Автоматические функции
- **Приветствие** — при первом сообщении в личке отправляет информацию об услугах.
- **Проверка онлайна** — если хозяин аккаунта оффлайн > 10 минут, бот отвечает, что «Флорест оффлайн», и просит подождать.
- **Обновление активности** — бот отслеживает исходящие сообщения, чтобы определить, когда хозяин был в сети.

### Команды (в исходящих сообщениях)

| Команда | Описание |
|---|---|
| `.stat` | Статистика чата (кол-во сообщений, участники) |
| `.deanon` | Информация о пользователе по номеру телефона (страна, регион, оператор) + аватар |
| `.photo` | Скачать аватарку пользователя |
| `.ai <текст>` | Запрос к GPT-5 через `g4f` (провайдер CopilotApp) |
| `.convert <сумма> <из> <в>` | Конвертация валют (USD/EUR/RUB) или единиц (KM/MI/KG/LB) |
| `.recog` (ответом на голосовое) | Распознавание речи (Google Speech, ru-RU) |
| `.download <url>` | Скачать видео/аудио с любого хостинга (через `yt-dlp`) |
| `.audio <url>` | Скачать только аудио (MP3, 192 kbps) |
| `.translate <язык>` (ответом на сообщение) | Перевод сообщения через GPT |
| `.weather <город>` | Погода через Open-Meteo |
| `.short <url>` | Сократить ссылку через TinyURL |
| `.time <город>` | Текущее время в городе (через GPT) |
| `.mood` | Анализ настроения чата по последним 20 сообщениям (через GPT) |

---

## 📋 Требования

- **Python 3.10+**
- **FFmpeg** (для конвертации аудио/видео)
- Аккаунт Telegram + `api_id` / `api_hash` из [my.telegram.org](https://my.telegram.org)

### Python-зависимости

```
telethon
phonenumbers
g4f
yt-dlp
requests
SpeechRecognition
```

Установка:

```bash
pip install -r requirements_telethon.txt
```

> `g4f` (gpt4free) — неофициальная библиотека, доступность провайдеров (`CopilotApp`, модель `gpt-5`) может меняться. При отказе провайдера команды `.ai`, `.translate`, `.time`, `.mood` перестанут работать — обнови `g4f` или смени провайдера.

---

## 🛠 Установка

### 1. Установи FFmpeg

**Windows** (через Chocolatey):
```powershell
choco install ffmpeg
```
или скачай с [ffmpeg.org](https://ffmpeg.org/download.html) и добавь в `PATH`.

**Linux (Debian/Ubuntu):**
```bash
sudo apt update && sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 2. Получи API-данные

1. Зайди на [my.telegram.org](https://my.telegram.org) → **API development tools**.
2. Создай приложение → получи `api_id` и `api_hash`.

### 3. Настрой скрипт

Открой `tg_utilits_telethon.py` и замени:

```python
api_id = 000000                    # ← твой api_id
api_hash = '0000000'               # ← твой api_hash
phone_number = '+79999999999'      # ← твой номер телефона
```

### 4. Первый запуск (авторизация)

```bash
python tg_utilits_telethon.py
```

При первом запуске Telethon попросит **код из Telegram** (и пароль 2FA, если включён).  
Файл сессии `session.session` сохранится рядом со скриптом — повторная авторизация не потребуется.

> 🔒 **Не публикуй** `session.session` и не выкладывай `api_hash` — это доступ к твоему аккаунту.

---

## ▶️ Запуск

```bash
python tg_utilits_telethon.py
```

В консоли появится `Бот запущен...` — бот начал слушать сообщения.

Останавливается через `Ctrl+C`.

### Автозапуск (Linux, systemd)

Создай `/etc/systemd/system/tg-utilits.service`:

```ini
[Unit]
Description=Telegram Utility Bot
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 /path/to/project/tg_utilits_telethon.py
Restart=on-failure
RestartSec=10
User=youruser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tg-utilits
sudo systemctl status tg-utilits
```

---

## 📁 Структура проекта

```
project/
├── tg_utilits_telethon.py   # основной скрипт
└── README.md
```

---

## ⚙️ Как это работает

- **`is_other_device_active()`** — через `account.GetAuthorizationsRequest` проверяет, была ли активность на других устройствах за последние 10 минут.
- **`last_activity`** — глобальная переменная, обновляется при каждом исходящем сообщении от тебя.
- **Обработчик `on_new_message`**:
  - Если сообщение входящее → проверяет онлайна (приветствие при первом сообщении, предупреждение при оффлайне).
  - Если исходящее → обновляет `last_activity` и разбирает команду (по префиксу).

---

## 🐛 Возможные проблемы

| Проблема | Решение |
|---|---|
| `ffmpeg not found` | Установи FFmpeg и добавь в `PATH` |
| `.recog` → `RequestError` | Google Speech API может блокироваться; проверь сеть/VPN |
| `.ai` / `.translate` → ошибка | `g4f` провайдер недоступен — обнови `g4f` или смени провайдера |
| `.download` не находит файл | Убедись, что ссылка поддерживается `yt-dlp` |
| `AuthKeyUnregistered` / сессия слетела | Удали `session.session` и авторизуйся заново |
| Бот не отвечает на входящие | Проверь, что в личке (бот обрабатывает только `is_private`) |
| `.recog` пишет «ответьте на голосовое» | Команду нужно отправлять **ответом** на голосовое сообщение |

---

## 🔐 Безопасность и этика

- Файл `session.session` = полный доступ к аккаунту. Не коммить в Git (добавь в `.gitignore`).
- `api_hash` тоже секретен.
- `.deanon` использует публичный номер из профиля пользователя — не применяй для вторжения в приватность.
- Массовая рассылка или автоматизация могут привести к **спам-блоку** аккаунта.

### `.gitignore`

```
session.session
*.session
*.session-journal
__pycache__/
*.pyc
.env
```

---

## 📄 Лицензия

Проект предоставляется «как есть» для личного использования. Автор не несёт ответственности за блокировку аккаунтов, нарушение ToS Telegram или законодательства при использовании бота.

---

## 🙋 Контакты

- ТГК: **@florestchannel**
- Отзывы: **@florest_otzyvi**
- Сайт: **florestone4185.ru**
