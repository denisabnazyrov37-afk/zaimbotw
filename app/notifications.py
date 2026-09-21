from aiogram import Bot
from aiogram.types import FSInputFile
from app.config import settings
from app.models import LoanApplication

async def notify_new_application(bot: Bot, app: LoanApplication):
    if not settings.notify_chat_id:
        return

    text = (
        f"🆕 Новая заявка #{app.id}\n\n"
        f"ФИО: {app.full_name}\n"
        f"Телефон: {app.phone}\n"
        f"Дата рождения: {app.birth_date}\n"
        f"Сумма: {app.amount}\n"
        f"Срок: {app.term_months} мес.\n"
        f"Статус: 🟡 рассмотрение\n\n"
        f"Команды:\n"
        f"/approve_{app.id}\n"
        f"/reject_{app.id}\n"
        f"/paid_{app.id}\n"
        f"/case_{app.id}"
    )
    await bot.send_message(settings.notify_chat_id, text)

    # Документы лучше не отправлять автоматически в чат.
    # Администратор может получить их через защищенный workflow.
