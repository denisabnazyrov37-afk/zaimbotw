# Telegram Loan Bot + Mini App + Contract PDF

## Что добавлено

- красивый Telegram Mini App;
- открытие Mini App кнопкой `🚀 Открыть приложение`;
- заполнение анкеты внутри Telegram;
- серверная проверка Telegram `initData`;
- сохранение заявки в SQLite;
- автоматическое формирование PDF-проекта договора на основе введённых данных;
- выдача PDF пользователю после одобрения;
- `/contract_ID` для повторной отправки проекта договора;
- сохранён обычный Telegram-бот и `/admin`.

## Настройка

В `bot.py` укажи:

```python
BOT_TOKEN = "токен"
ADMIN_IDS = {"123456789"}
MINI_APP_URL = "https://ТВОЙ-SERVICE.onrender.com/"
```

Для Render:

Build:
`pip install -r requirements.txt`

Start:
`python bot.py`

После первого deploy открой URL сервиса. Затем вставь этот URL в `MINI_APP_URL`, сделай commit/push и redeploy.

Также можно настроить Main Mini App через @BotFather. Telegram поддерживает запуск Mini Apps из кнопок и через меню бота. https://core.telegram.org/bots/webapps

## Договор

PDF сейчас является техническим **проектом/шаблоном договора**, а не гарантией юридической силы. Для реального сервиса отдельно требуется согласовать условия займа, проценты/неустойку, способ электронной подписи/заключения договора, подтверждение передачи денег и обработку персональных данных.

## Безопасность

Не публикуй настоящий BOT_TOKEN в открытом GitHub. Для production безопаснее хранить секреты в Render Environment Variables. В этой версии токен оставлен в `bot.py` по запросу пользователя.

Паспортные данные — чувствительная информация: используй тестовые данные до внедрения защищённого хранения и контроля доступа.


## Исправление Render

В этой версии исправлена ошибка `set_wakeup_fd only works in main thread`.
Telegram-бот и Flask Mini App работают в разных потоках, поэтому `run_polling()` запускается без установки Unix signal handlers (`stop_signals=[]`).


## Render event-loop fix

The final version runs Flask in a background thread and Telegram polling in the main thread. This avoids both `set_wakeup_fd` and `Cannot close a running event loop` errors caused by calling `run_polling()` inside a background thread/asyncio wrapper.
