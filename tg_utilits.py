import telebot
from telebot import types
import datetime
import tempfile
import os
import subprocess
import asyncio
import requests
import pathlib
import sys
import json
import threading
import importlib
from config import *

def llm7_chat(prompt: str, timeout: int = LLM7_TIMEOUT) -> str:
    """Синхронный вызов LLM7 (OpenAI-совместимый chat/completions)."""
    payload = {
        "model": LLM7_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Authorization": f"Bearer {LLM7_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    r = requests.post(
        LLM7_URL,
        headers=headers,
        data=json.dumps(payload),
        proxies=PROXIES,
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"LLM7 HTTP {r.status_code}: {r.text[:500]}")
    try:
        data = r.json()
    except Exception:
        return r.text

    choices = data.get('choices')
    if choices:
        msg = choices[0].get('message') or {}
        content = msg.get('content')
        if content:
            return content
        if 'text' in choices[0]:
            return choices[0]['text']

    if 'error' in data:
        err = data['error']
        if isinstance(err, dict) and 'message' in err:
            return f"LLM7 Error: {err['message']}"
        return f"LLM7 Error: {err}"

    return json.dumps(data, ensure_ascii=False)


bot = telebot.TeleBot(BOT_TOKEN)

message_counters = {}  # {(chat_id, user_id): count}

# ============ ХРАНИЛИЩЕ ВРЕМЕНИ ПОСЛЕДНЕГО СООБЩЕНИЯ ВЛАДЕЛЬЦА ============
# {chat_id: datetime последнего сообщения ОТ ВЛАДЕЛЬЦА (т.е. от бизнес-аккаунта)}
# В бизнес-чате сообщения владельца приходят с from_user == owner (тот, кто подключил business connection).
# Нам нужно знать id владельца для каждого connection.
# Словарь: {business_connection_id: owner_user_id}
connection_owners = {}

# {chat_id: datetime} — когда владелец последний раз писал в этот чат
owner_last_message = {}

# {chat_id: datetime} — когда бот последний раз отправлял автоответ в этот чат (антиспам)
autoreply_last_sent = {}

# Блокировка для потокобезопасности словарей
_state_lock = threading.Lock()

plugins_path = pathlib.Path(sys.argv[0]).parent.resolve() / 'plugins'

if not os.path.exists(plugins_path):
    os.mkdir(plugins_path)

import config
config_for_plugins = {
    k: v for k, v in config.__dict__.items() if not k.startswith('__')
}

for plugin_file in plugins_path.glob('*.py'):
    try:
        module_name = f"plugins.{plugin_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, 'run'): 
            print(f'[TG UTILITS] Добавь функцию `run` в файл `{plugin_file.stem}` или свяжись с разработчиком этого плагина.')
            raise Exception("Нет функции run")
        module.run(bot, **config_for_plugins)
        print(f"[TG UTILITS] Plugin '{plugin_file.stem}' loaded")
    except Exception as e:
            print(f"[TG UTILITS] Plugin error {plugin_file.stem}: {e}")

del config_for_plugins

def _conn(message):
    return getattr(message, 'business_connection_id', None)


def reply_biz(message, text, **kwargs):
    conn = _conn(message)
    return bot.send_message(
        message.chat.id, text,
        business_connection_id=conn,
        **kwargs
    )


def edit_biz(chat_id, message_id, text, conn, **kwargs):
    return bot.edit_message_text(
        text, chat_id, message_id,
        business_connection_id=conn, **kwargs
    )


# ============ BUSINESS CONNECTION ============
@bot.business_connection_handler()
def on_business_connection(connection: types.BusinessConnection):
    print(f'[Business] Подключён: id={connection.id}, user={connection.user.id}')
    with _state_lock:
        connection_owners[connection.id] = connection.user.id


# ============ АВТООТВЕТЧИК ============
def maybe_send_autoreply(message: types.Message, conn: str, owner_id: int):
    """
    Вызывается, когда пришло сообщение ОТ СОБЕСЕДНИКА (не от владельца).
    Проверяет: если владелец молчит > AUTOREPLY_TIMEOUT_MINUTES, и в этом чате
    ещё не отправляли автоответ после последнего сообщения владельца — отправляет.
    """
    chat_id = message.chat.id
    now = datetime.datetime.now(datetime.timezone.utc)

    with _state_lock:
        last_owner = owner_last_message.get(chat_id)
        last_auto = autoreply_last_sent.get(chat_id)

    # Если владелец вообще ни разу не писал — считаем, что «молчит давно»? 
    # Лучше НЕ спамить автоответом, пока владелец хоть раз не проявился. 
    # Если хочешь обратное поведение — убери этот блок.
    if last_owner is None:
        return

    delta_minutes = (now - last_owner).total_seconds() / 60.0
    if delta_minutes < AUTOREPLY_TIMEOUT_MINUTES:
        return

    # Не спамим: если уже отправляли автоответ ПОСЛЕ последнего сообщения владельца — выходим
    if last_auto is not None and last_auto >= last_owner:
        return

    try:
        bot.send_message(
            chat_id,
            AUTOREPLY_TEXT.replace("{name}", bot.get_business_connection(conn).user.full_name),
            business_connection_id=conn,
        )
        with _state_lock:
            autoreply_last_sent[chat_id] = now
        print(f'[Autoreply] Отправлен в чат {chat_id} (молчание {delta_minutes:.1f} мин)')
    except Exception as e:
        print(f'[Autoreply] Ошибка отправки в {chat_id}: {e}')


# ============ ОСНОВНОЙ ОБРАБОТЧИК ============
@bot.business_message_handler(content_types=['text', 'voice', 'photo', 'document', 'audio'])
def handle_business_message(message: types.Message):
    conn = _conn(message)
    if not conn:
        return

    chat_id = message.chat.id
    user = message.from_user
    text = message.text or ''
    now = datetime.datetime.now(datetime.timezone.utc)

    # --- Определяем, кто написал: владелец бизнес-аккаунта или собеседник ---
    is_owner = bot.get_business_connection(message.business_connection_id).user.id == message.from_user.id

    if is_owner:
        # Владелец написал — обновляем его "последнюю активность" и сбрасываем флаг автоответа
        with _state_lock:
            owner_last_message[chat_id] = now
            # автоответ можно будет снова отправить после следующего "молчания"
            autoreply_last_sent.pop(chat_id, None)
    else:
        # Собеседник написал — возможно, пора ответить автоответчиком
        maybe_send_autoreply(message, conn, is_owner)

    # --- Счётчик сообщений (считаем все сообщения в чате) ---
    key = (chat_id, user.id)
    message_counters[key] = message_counters.get(key, 0) + 1
    count = message_counters[key]

    try:
        if message.from_user.id != bot.get_business_connection(message.business_connection_id).user.id: return
        # ---------- .stat ----------
        if text.startswith('.stat'):
            reply_biz(message, f'Статистика чата:\nФлорест и {user.first_name}.\n\nКол-во сообщений: {count}')

        # ---------- .ai ----------
        elif text.startswith('.ai'):
            prompt = text[3:].strip() or text
            try:
                answer = llm7_chat(prompt)
            except Exception as e:
                answer = f'❌ Ошибка LLM7: {e}'
            reply_biz(message, f'Ответ от LLM7:\n```\n{answer}\n```', parse_mode='Markdown')

        # ---------- .convert ----------
        elif text.startswith('.convert'):
            parts = text[9:].split()
            if len(parts) < 3:
                reply_biz(message, '❌ Формат: `.convert 100 USD RUB`')
                return
            amount = float(parts[0])
            fu, tu = parts[1].upper(), parts[2].upper()
            if fu in ['USD', 'EUR', 'RUB']:
                r = requests.get(f'https://api.exchangerate-api.com/v4/latest/{fu}', timeout=15)
                rate = r.json()['rates'][tu]
                reply_biz(message, f'💱 {amount} {fu} = {amount * rate:.2f} {tu}')
            elif fu in ['KM', 'MI', 'KG', 'LB']:
                conv = {'KM_MI': 0.621371, 'MI_KM': 1.60934, 'KG_LB': 2.20462, 'LB_KG': 0.453592}
                k = f'{fu}_{tu}'
                if k in conv:
                    reply_biz(message, f'📐 {amount} {fu} = {amount * conv[k]:.2f} {tu}')
                else:
                    reply_biz(message, '❌ Неизвестная пара единиц')
            else:
                reply_biz(message, '❌ Неизвестные единицы')

        # ---------- .recog ----------
        elif text.startswith('.recog'):
            if not message.reply_to_message or not message.reply_to_message.voice:
                reply_biz(message, '❌ Ответьте на голосовое сообщение командой .recog')
                return

            status = reply_biz(message, '⏳ Скачиваю голосовое...')
            voice = message.reply_to_message.voice
            file_info = bot.get_file(voice.file_id)
            downloaded = bot.download_file(file_info.file_path)

            with tempfile.TemporaryDirectory() as td:
                ogg_path = os.path.join(td, 'voice.ogg')
                wav_path = os.path.join(td, 'voice.wav')
                with open(ogg_path, 'wb') as f:
                    f.write(downloaded)

                edit_biz(chat_id, status.message_id, '🔄 Конвертирую в WAV...', conn)
                try:
                    subprocess.run([
                        'ffmpeg', '-i', ogg_path,
                        '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                        '-y', wav_path
                    ], check=True, capture_output=True, timeout=30)
                except Exception as e:
                    edit_biz(chat_id, status.message_id, f'❌ Ошибка ffmpeg: {e}', conn)
                    return

                edit_biz(chat_id, status.message_id, '🎙️ Распознаю речь...', conn)
                import speech_recognition as sr
                rec = sr.Recognizer()
                try:
                    with sr.AudioFile(wav_path) as src:
                        data = rec.record(src)
                        recognized = rec.recognize_google(data, language='ru-RU')
                except sr.UnknownValueError:
                    edit_biz(chat_id, status.message_id, '❌ Не удалось распознать речь', conn)
                    return
                except sr.RequestError:
                    edit_biz(chat_id, status.message_id, '❌ Ошибка Google Speech API', conn)
                    return

                edit_biz(chat_id, status.message_id, f'📝 **Расшифровка:**\n\n{recognized}', conn, parse_mode='Markdown')

        # ---------- .download ----------
        elif text.startswith('.download'):
            parts = text.split()
            if len(parts) < 2:
                reply_biz(message, '❌ Укажите ссылку: `.download https://...`')
                return
            url = parts[1]
            status = reply_biz(message, '⏳ Анализирую ссылку...')
            try:
                import yt_dlp
                import glob
                with tempfile.TemporaryDirectory() as td:
                    ydl_opts = {
                        'outtmpl': f'{td}/%(title)s.%(ext)s',
                        'format': 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best',
                        'quiet': True, 'no_warnings': True,
                        'proxy':PROXIES.get('http'),
                        'restrictfilenames': True,
                        'noplaylist': True, 'no_part': True,
                        'postprocessor_args': ['-strict', '-2'],
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        edit_biz(chat_id, status.message_id, '📥 Скачиваю...', conn)
                        info = ydl.extract_info(url, download=True)
                        if not info:
                            edit_biz(chat_id, status.message_id, '❌ Не удалось получить информацию', conn)
                            return
                        filename = ydl.prepare_filename(info)
                        if not os.path.exists(filename):
                            files = glob.glob(f'{td}/*.mp4') + glob.glob(f'{td}/*.mp3')
                            if not files:
                                edit_biz(chat_id, status.message_id, '❌ Файл не найден', conn)
                                return
                            filename = files[0]

                    size_mb = os.path.getsize(filename) / (1024 * 1024)
                    if size_mb > 2000:
                        edit_biz(chat_id, status.message_id, f'❌ Файл слишком большой ({size_mb:.1f}MB)', conn)
                        return

                    title = (info.get('title') or 'Файл')[:97]
                    ext = os.path.splitext(filename)[1].lower()
                    is_audio = ext in ['.mp3', '.m4a', '.aac', '.flac', '.wav']
                    edit_biz(chat_id, status.message_id, f'📤 Отправляю: {title}', conn)

                    with open(filename, 'rb') as f:
                        if is_audio:
                            bot.send_audio(chat_id, f, caption=f'🎵 {title}', business_connection_id=conn)
                        else:
                            bot.send_video(chat_id, f, caption=f'🎬 {title}', business_connection_id=conn, supports_streaming=True)

                    edit_biz(chat_id, status.message_id, f'✅ Готово! {title}', conn)
            except Exception as e:
                reply_biz(message, f'❌ Ошибка: {e}')

        # ---------- .audio ----------
        elif text.startswith('.audio'):
            parts = text.split()
            if len(parts) < 2:
                reply_biz(message, '❌ Укажите ссылку: `.audio https://...`')
                return
            url = parts[1]
            status = reply_biz(message, '⏳ Загружаю аудио...')
            try:
                import yt_dlp
                import glob
                with tempfile.TemporaryDirectory() as td:
                    ydl_opts = {
                        'outtmpl': f'{td}/%(title)s.%(ext)s',
                        'format': 'bestaudio/best',
                        'proxy':PROXIES.get('http'),
                        'quiet': True, 'no_warnings': True,
                        'restrictfilenames': True, 'noplaylist': True,
                        'postprocessor_args': ['-strict', '-2'],
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        edit_biz(chat_id, status.message_id, '📥 Скачиваю аудио...', conn)
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
                        if not os.path.exists(filename):
                            files = glob.glob(f'{td}/*.mp3')
                            if not files:
                                edit_biz(chat_id, status.message_id, '❌ Аудио не найдено', conn)
                                return
                            filename = files[0]

                    size_mb = os.path.getsize(filename) / (1024 * 1024)
                    if size_mb > 2000:
                        edit_biz(chat_id, status.message_id, f'❌ Файл слишком большой ({size_mb:.1f}MB)', conn)
                        return

                    title = (info.get('title') or 'Аудио')[:97]
                    edit_biz(chat_id, status.message_id, f'📤 Отправляю аудио: {title}', conn)
                    with open(filename, 'rb') as f:
                        bot.send_audio(chat_id, f, caption=f'🎵 {title}', business_connection_id=conn)
                    edit_biz(chat_id, status.message_id, f'✅ Аудио готово! {title}', conn)
            except Exception as e:
                reply_biz(message, f'❌ Ошибка: {e}')

        # ---------- .translate ----------
        elif text.startswith('.translate'):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                reply_biz(message, '❌ Формат: `.translate en` (ответом на сообщение)')
                return
            lang = parts[1].strip()
            if not message.reply_to_message or not message.reply_to_message.text:
                reply_biz(message, '❌ Ответьте на текстовое сообщение')
                return
            src_text = message.reply_to_message.text
            try:
                translated = llm7_chat(
                    f'Переведи это сообщение: {src_text}\nНа язык: {lang}\nБЕЗ СВОИХ КОММЕНТАРИЕВ'
                )
            except Exception as e:
                translated = f'❌ Ошибка LLM7: {e}'
            reply_biz(message, f'Перевод: ```\n{translated}\n```', parse_mode='Markdown')

        # ---------- .weather ----------
        elif text.startswith('.weather'):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                reply_biz(message, '❌ Введи город: `.weather Москва`')
                return
            city = parts[1].strip()
            status = reply_biz(message, f'🌤️ Смотрю в окно в {city}...')
            try:
                geo = requests.get(
                    f'https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1',
                    timeout=15
                ).json()
                if not geo.get('results'):
                    edit_biz(chat_id, status.message_id, f'❌ Город "{city}" не найден', conn)
                    return
                lat = geo['results'][0]['latitude']
                lon = geo['results'][0]['longitude']
                data = requests.get(
                    f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&timezone=auto',
                    timeout=15
                ).json()
                cur = data['current_weather']
                codes = {
                    0: '☀️ Ясно', 1: '🌤️ Слегка облачно', 2: '⛅ Переменная облачность',
                    3: '☁️ Пасмурно', 45: '🌫️ Туман', 48: '🌫️ Туман с изморозью',
                    51: '🌧️ Легкая морось', 53: '🌧️ Умеренная морось', 55: '🌧️ Сильная морось',
                    61: '🌧️ Легкий дождь', 63: '🌧️ Умеренный дождь', 65: '🌧️ Сильный дождь',
                    71: '🌨️ Легкий снегопад', 73: '🌨️ Умеренный снегопад', 75: '🌨️ Сильный снегопад',
                    80: '🌧️ Ливень', 81: '🌧️ Умеренный ливень', 82: '🌧️ Сильный ливень',
                    95: '⛈️ Гроза', 96: '⛈️ Гроза с градом', 99: '⛈️ Сильная гроза с градом',
                }
                wtext = codes.get(cur['weathercode'], f'❓ Код {cur["weathercode"]}')
                wd = cur.get('winddirection', 0)
                dirs = ['⬆️ С', '↗️ СВ', '➡️ В', '↘️ ЮВ', '⬇️ Ю', '↙️ ЮЗ', '⬅️ З', '↖️ СЗ']
                wicon = dirs[int((wd % 360) / 45)] if wd is not None else '❓'
                try:
                    dt = datetime.datetime.fromisoformat(cur.get('time', '').replace('Z', '+00:00'))
                    tstr = dt.strftime('%H:%M')
                except Exception:
                    tstr = cur.get('time', '')
                out = (
                    f"🌤️ **Погода в {city.title()}**\n\n"
                    f"🌡️ Температура: **{cur['temperature']}°C**\n"
                    f"{wtext}\n"
                    f"💨 Ветер: {wicon} **{cur.get('windspeed', 0)} м/с**\n"
                    f"🕐 Обновлено: {tstr}"
                )
                edit_biz(chat_id, status.message_id, out, conn, parse_mode='Markdown')
            except Exception as e:
                edit_biz(chat_id, status.message_id, f'❌ Ошибка: {e}', conn)

        # ---------- .short ----------
        elif text.startswith('.short'):
            url = text[6:].strip()
            if not url:
                reply_biz(message, '❌ Введи ссылку: `.short https://...`')
                return
            status = reply_biz(message, '🔗 Сокращаю...')
            try:
                r = requests.get(f'https://tinyurl.com/api-create.php?url={url}', timeout=15)
                if r.status_code == 200:
                    edit_biz(chat_id, status.message_id, f'🔗 **Короткая ссылка:**\n{r.text}', conn, parse_mode='Markdown')
                else:
                    edit_biz(chat_id, status.message_id, '❌ Ошибка сокращения', conn)
            except Exception as e:
                edit_biz(chat_id, status.message_id, f'❌ Ошибка: {e}', conn)

        # ---------- .time ----------
        elif text.startswith('.time'):
            city = text[5:].strip() or 'Москва'
            status = reply_biz(message, f'🕐 Узнаю время в {city}...')
            try:
                time_str = llm7_chat(
                    f"Скажи текущее время в городе {city}. Только время, без лишнего текста. Формат: 12:34"
                )
            except Exception as e:
                time_str = f'❌ Ошибка LLM7: {e}'
            edit_biz(chat_id, status.message_id,
                     f'🕐 **Время в {city}:**\n{time_str}', conn,
                     parse_mode='Markdown')

        # ---------- .mood ----------
        elif text.startswith('.mood'):
            status = reply_biz(message, '🧠 Анализирую настроение...')
            try:
                mood = llm7_chat(
                    f"Проанализируй настроение чата по сообщению:\n{text}\n\nДай краткий анализ (1-2 предложения) и эмодзи."
                )
            except Exception as e:
                mood = f'❌ Ошибка LLM7: {e}'
            edit_biz(chat_id, status.message_id,
                     f'📊 **Настроение чата:**\n\n{mood}', conn,
                     parse_mode='Markdown')

                # ---------- .help ----------
        elif text.startswith('.help') or text == '/help':
            help_text = (
                "🤖 <b>Справка по боту</b>\n\n"
                "Все команды пишутся в чат и начинаются с точки <code>.</code>\n\n"
                "🧠 <b>AI и перевод</b>\n"
                "<code>.ai &lt;запрос&gt;</code> — ответ от LLM7\n"
                "<code>.translate &lt;язык&gt;</code> — перевод (ответом на сообщение)\n"
                "<code>.mood</code> — анализ настроения сообщения\n"
                "<code>.time &lt;город&gt;</code> — время в городе (через LLM)\n\n"
                "🎬 <b>Медиа</b>\n"
                "<code>.download &lt;url&gt;</code> — скачать видео/аудио по ссылке\n"
                "<code>.audio &lt;url&gt;</code> — скачать только аудио (mp3)\n"
                "<code>.recog</code> — распознать голосовое (ответом на voice)\n\n"
                "🛠 <b>Инструменты</b>\n"
                "<code>.convert 100 USD RUB</code> — конвертация валют/единиц\n"
                "<code>.weather &lt;город&gt;</code> — погода\n"
                "<code>.short &lt;url&gt;</code> — сократить ссылку\n\n"
                "ℹ️ <b>О боте</b>\n"
                f"• Автоответчик: если владелец молчит &gt; {AUTOREPLY_TIMEOUT_MINUTES} мин — бот ответит автоматически\n"
                "• AI-движок: LLM7"
            )
            reply_biz(message, help_text, parse_mode='HTML')

    except Exception as e:
        try:
            reply_biz(message, f'❌ Внутренняя ошибка: {e}')
        except Exception:
            pass


print('Бот запущен (LLM7 + автоответчик 30 мин)...')
bot.infinity_polling(timeout=60, long_polling_timeout=60)