from telethon.sync import TelegramClient
from telethon import events, types, functions
import datetime
import phonenumbers
from phonenumbers import geocoder, carrier
import tempfile
from g4f.client import AsyncClient as Client
from g4f.Provider import CopilotApp
import subprocess
import os
import yt_dlp
import asyncio
import requests
import pathlib, sys
from vk_api import VkApi

api_id = 23366542
api_hash = 'c3d29df48b0bb32d564e82b344eba0c8'
phone_number = '+79787661757'
last_activity = None
client = Client()
path = pathlib.Path(sys.argv[0]).parent.resolve()

tg = TelegramClient(path / 'florestone4185_session', api_id, api_hash, app_version='4.16.30-vxCUSTOM', system_version='Win11', device_model='ASUS PRO HAH 111')
tg.start(phone=phone_number)

async def is_other_device_active():
    """Проверяет, активно ли другое устройство (кроме Telethon)"""
    try:
        result = await tg(functions.account.GetAuthorizationsRequest())
        
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        current_hash = None
        
        # Находим текущую сессию (Telethon)
        for auth in result.authorizations:
            if auth.current:
                current_hash = auth.hash
                break
        
        # Проверяем другие сессии
        for auth in result.authorizations:
            if auth.hash == current_hash:
                continue
            
            # Если устройство активно в течение последних 10 минут
            if (now - auth.date_active).total_seconds() < 600:  # 10 минут
                print(f"✅ Активно: {auth.device_model} - {auth.date_active}")
                return True
        
        print("❌ Нет активных устройств")
        return False
        
    except Exception as e:
        print(f"Ошибка при проверке сессий: {e}")
        return False


@tg.on(events.NewMessage(func=lambda e: e.is_private))
async def on_new_message(event: types.Message):
    global last_activity  # ✅ ДОЛЖНА БЫТЬ ПЕРВОЙ СТРОКОЙ ВНУТРИ ФУНКЦИИ
    
    # Проверяем, что сообщение входящее (не от нас)
    if not event.out:
        # Получаем количество сообщений в диалоге
        messages = await tg.get_messages(event.sender_id, limit=1)
        count = messages.total
        
        # Если это первое сообщение
        if count == 1:
            await event.reply(
                'Здравствуйте! Меня зовут Флорест.\n'
                'Предоставляю: **услуги программирования**, '
                '**создание Minecraft серверов**, **другие услуги**.\n\n'
                'ТГК: @florestchannel\n'
                'Отзывы: @florest_otzyvi\n'
                'Сайт: florestone4185.ru'
            )
            return  # ⬅️ Добавь, чтобы не проверять активность после приветствия
        
        # Проверяем активность
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        
        if last_activity is not None:
            # Проверяем, когда была последняя активность
            if (now - last_activity).total_seconds() > 600:
                await event.reply(
                    'Извините, но **Флорест** оффлайн уже свыше 10 минут. '
                    'Пожалуйста, дождитесь его захода в сеть.'
                )
        else:
            # Если last_activity None - проверяем через сессии
            if not await is_other_device_active():
                await event.reply(
                    'Извините, но **Флорест** оффлайн уже свыше 10 минут. '
                    'Пожалуйста, дождитесь его захода в сеть.'
                )
    else:
        # Это исходящее сообщение (мы написали кому-то)
        # Обновляем время последней активности
        last_activity = datetime.datetime.now(datetime.timezone.utc).astimezone()
        print(f"🔄 Обновлена активность: {last_activity}")
        messages = await tg.get_messages(event.sender_id, limit=1)
        count = messages.total

        if event.text.startswith('.stat'):
            user = await tg.get_entity(event.peer_id)
            await event.reply(f'Статистика чата:\nФлорест и {user.first_name}.\n\nКол-во сообщений: {count}')
        elif event.text.startswith('.deanon'):
            user = await tg.get_entity(event.peer_id)
            phone = user.phone
            print(user.phone)
            data = 'Нет данных'
            if phone:
                parsed = phonenumbers.parse(f'+{phone}', _check_region=False)
                country_code = parsed.country_code
                country_name = geocoder.country_name_for_number(parsed, "ru")
                region = geocoder.description_for_number(parsed, "ru")
                carrier_name = carrier.name_for_number(parsed, "ru")
                data = f'Данные о {user.first_name}:\nКод страны: {country_code if country_code else "Неизвестно"}\nИмя страны: {country_name if country_name else "Неизвестно"}\nРегион: {region if region else "Неизвестно"}\nОператор: {carrier_name if carrier_name else "Неизвестно"}'
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name
            photo_bytes = await tg.download_profile_photo(user, file=tmp_path)
            await tg.send_file(user, tmp_path, caption=data, force_document=False)
        elif event.text.startswith('.photo'):
            user = await tg.get_entity(event.peer_id)
            if not user.photo:
                await event.reply(f'У пользователя нет аватарки.')
                return
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name
            photo_bytes = await tg.download_profile_photo(user, file=tmp_path)
            await tg.send_file(user, tmp_path, caption=f'Аватарка {user.first_name}', force_document=False)
        elif event.text.startswith('.ai'):
            response = await client.chat.completions.create([{"role":"user", "content":event.text}], 'gpt-5', CopilotApp, max_tokens=1500, proxy='http://Qh0wG0:eqJZ4z@185.104.148.124:8000')
            await tg.send_message(event.peer_id, f'Ответ от GPT:\n```\n{response.choices[0].message.content}\n```', parse_mode='Markdown')
        elif event.text.startswith('.convert'):
            import requests
            # .convert 100 USD RUB
            # .convert 5 km mi
            parts = event.text[9:].split()
            amount = float(parts[0])
            from_unit = parts[1].upper()
            to_unit = parts[2].upper()
            
            # Валюты через API
            if from_unit in ['USD', 'EUR', 'RUB']:
                response = requests.get(f'https://api.exchangerate-api.com/v4/latest/{from_unit}')
                rate = response.json()['rates'][to_unit]
                result = amount * rate
                await event.reply(f'💱 {amount} {from_unit} = {result:.2f} {to_unit}')
            
            # Единицы измерения
            elif from_unit in ['KM', 'MI', 'KG', 'LB']:
                conversions = {'KM_MI': 0.621371, 'MI_KM': 1.60934, 'KG_LB': 2.20462, 'LB_KG': 0.453592}
                key = f'{from_unit}_{to_unit}'
                if key in conversions:
                    result = amount * conversions[key]
                    await event.reply(f'📐 {amount} {from_unit} = {result:.2f} {to_unit}')
        elif event.text.startswith('.balance'):
            import requests
            response = await event.reply(f'Получаю данные от оператора связи...')
            session = requests.Session()
            session.proxies = {'http':'http://Qh0wG0:eqJZ4z@185.104.148.124:8000', 'https':"http://Qh0wG0:eqJZ4z@185.104.148.124:8000"}
            session.headers = {"User-Agent": "Mozilla/5.0"}
            api = VkApi(token='vk1.a.V_teWPPJxde9ZPF2K5_6DSJPefXeE7K1lMlift2HEZqxLbeq4cv1Oj5opgsG5GfzHLaSx-kLoRdmjzPh25xTkaVV1yC1fB7fYVQprlhz69CjmoTYfPbMRJO8oR9Po4JuQBlYaAWNHj7Ol6w92FvJ3-bxL2Ffm9eRwOx6JL71szkCQs0xBkQoIYSvN7ikw0TDtzzx0de7QdHHtnYFfMvMvg', session=session)
            methods = api.get_api()
            peer_id = None
            try:
                # Передаем короткое имя без символа '@'
                resolved = methods.utils.resolveScreenName(screen_name='phoenix7949')
                if resolved and resolved['type'] == 'group':
                    group_id = resolved['object_id']  # Это число и будет ID группы
                    peer_id = -group_id  # Для отправки сообщения в группу ставим минус
                    print(f"Найден ID группы: {group_id}")
                    # Теперь можно отправлять сообщение на peer_id
                else:
                    print("Группа с таким именем не найдена.")
            except Exception as e:
                print(f"Ошибка при поиске группы: {e}")
            try:
            # 2. Отправляем сообщение "Баланс"
                methods.messages.send(
                    peer_id=peer_id,
                    message="💰Проверка баланса",
                    random_id=0  # Уникальный ID для предотвращения дублирования
                )
                print(f"✅ Сообщение отправлено в группу {group_id}")
                await response.edit('⏳ Ожидаю ответ от оператора...')
                
                # 3. Ждем ответ (даем время боту оператора ответить)
                await asyncio.sleep(5)
                
                # 4. Получаем последние сообщения от группы
                messages = methods.messages.getHistory(
                    peer_id=peer_id,
                    count=5,  # Берем последние 5 сообщений
                    rev=0  # 0 - сначала старые, 1 - сначала новые
                )
                
                # 5. Ищем ответ от группы (не наше сообщение)
                operator_response = None
                for msg in messages['items']:
                    # Проверяем, что сообщение от группы (from_id отрицательный)
                    if msg['from_id'] < 0 and msg['from_id'] == peer_id:
                        operator_response = msg['text']
                        break
                
                if not operator_response:
                    await response.edit('❌ Не удалось получить ответ от оператора. Попробуйте позже.')
                    return
                await response.edit(operator_response)
            except Exception as e:
                print(f'Ошибка: {e}')
        elif event.text.startswith('.recog'):
    # Проверяем, есть ли ответ на голосовое
            if not event.reply_to.reply_to_msg_id:
                await event.reply('❌ Ответьте на голосовое сообщение командой .recog')
                return
            
            # Получаем голосовое сообщение
            reply_msg = await tg.get_messages(event.chat_id, ids=event.reply_to.reply_to_msg_id)
            if not reply_msg.voice:
                await event.reply('❌ Это не голосовое сообщение')
                return
            
            # Отправляем статус
            status_msg = await event.reply('⏳ Скачиваю голосовое...')
            
            # Скачиваем .ogg
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
                ogg_path = tmp.name
            await tg.download_media(reply_msg.voice, file=ogg_path)
            
            await status_msg.edit('🔄 Конвертирую в WAV...')
            
            # Конвертируем ogg -> wav через ffmpeg
            wav_path = ogg_path.replace('.ogg', '.wav')
            try:
                subprocess.run([
                    'ffmpeg',
                    '-i', ogg_path,           # входной файл
                    '-acodec', 'pcm_s16le',   # кодек
                    '-ar', '16000',           # частота (16kHz для SR)
                    '-ac', '1',               # моно
                    '-y',                     # перезаписать
                    wav_path
                ], check=True, capture_output=True, timeout=30)
            except subprocess.TimeoutExpired:
                await status_msg.edit('❌ Конвертация заняла слишком много времени')
                os.unlink(ogg_path)
                return
            except subprocess.CalledProcessError as e:
                await status_msg.edit(f'❌ Ошибка ffmpeg: {e.stderr.decode()}')
                os.unlink(ogg_path)
                return
            
            await status_msg.edit('🎙️ Распознаю речь...')
            
            # Распознаем через speech_recognition
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            try:
                with sr.AudioFile(wav_path) as source:
                    # Улучшаем качество распознавания
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data, language='ru-RU')
            except sr.UnknownValueError:
                await status_msg.edit('❌ Не удалось распознать речь')
                os.unlink(ogg_path)
                os.unlink(wav_path)
                return
            except sr.RequestError:
                await status_msg.edit('❌ Ошибка подключения к Google Speech API')
                os.unlink(ogg_path)
                os.unlink(wav_path)
                return
            
            # Отправляем результат
            await status_msg.edit(f'📝 **Расшифровка:**\n\n{text}')
            
            # Чистим файлы
            os.unlink(ogg_path)
            os.unlink(wav_path)
        elif event.text.startswith('.download'):
            try:
                # Проверяем ссылку
                parts = event.text.split()
                if len(parts) < 2:
                    await event.reply('❌ Укажите ссылку: `.download https://youtu.be/...`')
                    return
                
                url = parts[1]
                
                # Отправляем статус
                status = await event.reply('⏳ Анализирую ссылку...')
                
                # Создаём временную папку
                with tempfile.TemporaryDirectory() as tmpdir:
                    # Настройки yt-dlp для всех хостингов
                    ydl_opts = {
                        'outtmpl': f'{tmpdir}/%(title)s.%(ext)s',
                        'format': 'best[ext=mp4]/best[ext=mp3]/best',
                        'quiet': True,
                        'no_warnings': True,
                        'merge_output_format': 'mp4',
                        'restrictfilenames': True,
                        'noplaylist': True,  # Только одно видео
                        'no_part': True,     # Не сохранять части
                        'ignoreerrors': True,
                        'extract_flat': False,
                        'postprocessors': [{
                            'key': 'FFmpegVideoConvertor',
                            'preferedformat': 'mp4',
                        }],
                        # Поддержка всех популярных хостингов
                        'extractor_args': {
                            'youtube': {
                                'skip': ['dash', 'hls'],  # Пропускаем DASH для стабильности
                            }
                        }
                    }
                    
                    # Создаём загрузчик
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        await status.edit('📥 Скачиваю...')
                        
                        try:
                            # Получаем информацию и скачиваем
                            info = ydl.extract_info(url, download=True)
                            
                            if info is None:
                                await status.edit('❌ Не удалось получить информацию о видео')
                                return
                            
                            # Получаем имя файла
                            filename = ydl.prepare_filename(info)
                            
                            # Если файл не найден, пробуем найти любой .mp4 или .mp3
                            if not os.path.exists(filename):
                                import glob
                                files = glob.glob(f'{tmpdir}/*.mp4') + glob.glob(f'{tmpdir}/*.mp3')
                                if files:
                                    filename = files[0]
                                else:
                                    await status.edit('❌ Файл не найден после скачивания')
                                    return
                            
                        except Exception as e:
                            await status.edit(f'❌ Ошибка скачивания: {str(e)}')
                            return
                    
                    # Проверяем размер
                    file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
                    if file_size > 2000:  # 2GB лимит Telegram
                        await status.edit(f'❌ Файл слишком большой ({file_size:.1f}MB > 2GB)')
                        return
                    
                    # Определяем тип файла
                    file_ext = os.path.splitext(filename)[1].lower()
                    is_audio = file_ext in ['.mp3', '.m4a', '.aac', '.flac', '.wav']
                    
                    # Получаем название
                    title = info.get('title', 'Файл')
                    if len(title) > 100:
                        title = title[:97] + '...'
                    
                    # Отправляем
                    await status.edit(f'📤 Отправляю: {title}')
                    
                    if is_audio:
                        await tg.send_file(
                            event.chat_id,
                            filename,
                            caption=f'🎵 {title}',
                            voice_note=False,
                            supports_streaming=True
                        )
                    else:
                        await tg.send_file(
                            event.chat_id,
                            filename,
                            caption=f'🎬 {title}',
                            supports_streaming=True,
                            video_note=False
                        )
                    
                    await status.edit(f'✅ Готово! {title}')
                    
                    # Файлы удалятся автоматически при выходе из контекста
                    
            except Exception as e:
                await event.reply(f'❌ Ошибка: {str(e)}')

        # Команда для скачивания только аудио
        elif event.text.startswith('.audio'):
            try:
                parts = event.text.split()
                if len(parts) < 2:
                    await event.reply('❌ Укажите ссылку: `.audio https://youtu.be/...`')
                    return
                
                url = parts[1]
                status = await event.reply('⏳ Загружаю аудио...')
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    ydl_opts = {
                        'outtmpl': f'{tmpdir}/%(title)s.%(ext)s',
                        'format': 'bestaudio/best',
                        'quiet': True,
                        'no_warnings': True,
                        'restrictfilenames': True,
                        'noplaylist': True,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'extract_flat': False,
                    }
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        await status.edit('📥 Скачиваю аудио...')
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
                        
                        if not os.path.exists(filename):
                            import glob
                            files = glob.glob(f'{tmpdir}/*.mp3')
                            if files:
                                filename = files[0]
                            else:
                                await status.edit('❌ Аудио не найдено')
                                return
                        
                        file_size = os.path.getsize(filename) / (1024 * 1024)
                        if file_size > 2000:
                            await status.edit(f'❌ Файл слишком большой ({file_size:.1f}MB > 2GB)')
                            return
                        
                        title = info.get('title', 'Аудио')
                        if len(title) > 100:
                            title = title[:97] + '...'
                        
                        await status.edit(f'📤 Отправляю аудио: {title}')
                        await tg.send_file(
                            event.chat_id,
                            filename,
                            caption=f'🎵 {title}',
                            voice_note=False,
                            supports_streaming=True
                        )
                        
                        await status.edit(f'✅ Аудио готово! {title}')
                        
            except Exception as e:
                await event.reply(f'❌ Ошибка: {str(e)}')
        elif event.text.startswith('.translate'):
            lang = event.text.split()[1]
            reply_msg = await tg.get_messages(event.chat_id, ids=event.reply_to.reply_to_msg_id)
            response = await client.chat.completions.create([{"role":"user", "content":f'Переведи это сообщение: {reply_msg.text}\nНа язык: {lang}\nБЕЗ СВОИХ КОММЕНТАРИЕВ'}], 'gpt-5', CopilotApp)
            await tg.send_message(event.peer_id, f'Перевод: ```\n{response.choices[0].message.content}\n```', parse_mode='Markdown')
        elif event.text.startswith('.weather'):
            parts = event.text.split()
            if len(parts) < 2:
                await event.reply('❌ А город введи, экстрасенс я что ли? `.weather Москва`')
                return
            
            city = ' '.join(parts[1:])
            status = await event.reply(f'🌤️ Смотрю в окно в {city}...')
            
            try:
                import requests
                # Ищем город
                geo_response = requests.get(
                    f'https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1'
                )
                
                if geo_response.status_code != 200:
                    await status.edit('🌧️ Что-то сломалось... Попробуй позже')
                    return
                
                geo_data = geo_response.json()
                
                if not geo_data.get('results'):
                    await status.edit(f'❌ Город "{city}" не найден. Проверь название!')
                    return
                
                # Получаем координаты (правильно!)
                lat = geo_data['results'][0]['latitude']
                lon = geo_data['results'][0]['longitude']
                
                # Запрашиваем погоду
                weather_response = requests.get(
                    f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&timezone=auto'
                )
                
                if weather_response.status_code != 200:
                    await status.edit('🌧️ Не удалось получить погоду. Попробуй позже')
                    return
                
                data = weather_response.json()
                current = data['current_weather']
                
                # Расшифровка кодов погоды
                weather_codes = {
                    0: '☀️ Ясно',
                    1: '🌤️ Слегка облачно',
                    2: '⛅ Переменная облачность',
                    3: '☁️ Пасмурно',
                    45: '🌫️ Туман',
                    48: '🌫️ Туман с изморозью',
                    51: '🌧️ Легкая морось',
                    53: '🌧️ Умеренная морось',
                    55: '🌧️ Сильная морось',
                    61: '🌧️ Легкий дождь',
                    63: '🌧️ Умеренный дождь',
                    65: '🌧️ Сильный дождь',
                    71: '🌨️ Легкий снегопад',
                    73: '🌨️ Умеренный снегопад',
                    75: '🌨️ Сильный снегопад',
                    80: '🌧️ Ливень',
                    81: '🌧️ Умеренный ливень',
                    82: '🌧️ Сильный ливень',
                    95: '⛈️ Гроза',
                    96: '⛈️ Гроза с градом',
                    99: '⛈️ Сильная гроза с градом'
                }
                
                weather_text = weather_codes.get(current['weathercode'], f'❓ Неизвестно (код: {current["weathercode"]})')
                
                # Направление ветра
                wind_dir = current.get('winddirection', 0)
                directions = ['⬆️ С', '↗️ СВ', '➡️ В', '↘️ ЮВ', '⬇️ Ю', '↙️ ЮЗ', '⬅️ З', '↖️ СЗ']
                wind_icon = directions[int((wind_dir % 360) / 45)] if wind_dir is not None else '❓'
                
                # Время
                time_str = current.get('time', '')
                try:
                    dt = datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    time_formatted = dt.strftime('%H:%M')
                except:
                    time_formatted = time_str
                
                # Собираем ответ
                response = f"""🌤️ **Погода в {city.title()}**

        🌡️ Температура: **{current['temperature']}°C**
        {weather_text}
        💨 Ветер: {wind_icon} **{current.get('windspeed', 0)} м/с**
        🕐 Обновлено: {time_formatted}

        💡 *Влажность и давление можно посмотреть по ссылке в браузере*"""
                
                await status.edit(response)
                
            except Exception as e:
                await status.edit(f'❌ Что-то пошло не так: {str(e)}')
        elif event.text.startswith('.gif'):
            query = event.text[5:].strip()
            if not query:
                await event.reply('❌ Введи запрос: `.gif смешной кот`')
                return
            
            status = await event.reply('🔍 Ищу GIF...')
            
            try:
                import requests
                # GIPHY API (бесплатный)
                api_key = "YOUR_GIPHY_API_KEY"  # Замени на свой
                response = requests.get(
                    f'https://api.giphy.com/v1/gifs/search',
                    params={
                        'api_key': api_key,
                        'q': query,
                        'limit': 3,
                        'rating': 'g'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['data']:
                        gif_url = data['data'][0]['images']['original']['url']
                        await tg.send_file(event.chat_id, gif_url, caption=f'🎬 {query}')
                        await status.delete()
                    else:
                        await status.edit('❌ GIF не найдены')
                else:
                    await status.edit('❌ Ошибка API')
                    
            except Exception as e:
                await status.edit(f'❌ Ошибка: {str(e)}')
        elif event.text.startswith('.short'):
            import requests
            url = event.text[7:].strip()
            if not url:
                await event.reply('❌ Введи ссылку: `.short https://...`')
                return
            
            status = await event.reply('🔗 Сокращаю...')
            
            try:
                response = requests.get(f'https://tinyurl.com/api-create.php?url={url}')
                if response.status_code == 200:
                    await status.edit(f'🔗 **Короткая ссылка:**\n{response.text}')
                else:
                    await status.edit('❌ Ошибка сокращения')
            except Exception as e:
                await status.edit(f'❌ Ошибка: {str(e)}')
        elif event.text.startswith('.time'):
            city = event.text[6:].strip() or "Москва"
            
            status = await event.reply(f'🕐 Узнаю время в {city}...')
            
            response = await client.chat.completions.create(
                [{"role": "user", "content": f"Скажи текущее время в городе {city}. Только время, без лишнего текста. Формат: 12:34"}],
                'gpt-5', CopilotApp
            )
            
            await status.edit(f'🕐 **Время в {city}:**\n{response.choices[0].message.content}')
        elif event.text.startswith('.mood'):
            messages = await tg.get_messages(event.chat_id, limit=20)
            texts = [msg.text for msg in messages if msg.text]
            
            if not texts:
                await event.reply('💬 В чате нет сообщений для анализа')
                return
            
            status = await event.reply('🧠 Анализирую настроение...')
            
            response = await client.chat.completions.create(
                [{"role": "user", "content": f"Проанализируй настроение чата по сообщениям:\n{chr(10).join(texts[:10])}\n\nДай краткий анализ (1-2 предложения) и эмодзи."}],
                'gpt-5', CopilotApp
            )
            
            await status.edit(f'📊 **Настроение чата:**\n\n{response.choices[0].message.content}')

print("Бот запущен...")
tg.run_until_disconnected()