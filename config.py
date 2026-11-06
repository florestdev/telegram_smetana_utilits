"MAIN CONFIG OF TELEGRAM UTILITS OF [FLORESTDEVELOPMENT](https://florestone4185.ru)"

# ============ НАСТРОЙКИ ============
BOT_TOKEN = 'token'
PROXY = 'http://abc:def@123.456.789.111:2022'
PROXIES = {'http': PROXY, 'https': PROXY}

# ============ LLM7 ============
LLM7_URL = 'https://api.llm7.io/v1/chat/completions'
LLM7_KEY = 'unused'
LLM7_MODEL = 'default'
LLM7_TIMEOUT = 300

# ============ АВТООТВЕТЧИК ============
AUTOREPLY_TIMEOUT_MINUTES = 30  # через сколько минут молчания владельца включать автоответчик

AUTOREPLY_TEXT = (
    "👋 Я - FlorestBot.\n"
    "{name} сейчас занят(а) и не может ответить на Ваше сообщение.\n "
    "Дождитесь его ответа."
)
