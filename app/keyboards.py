from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Подать заявку")],
            [KeyboardButton(text="📋 Мои заявки")],
        ],
        resize_keyboard=True,
    )

def yes_no(prefix: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"{prefix}:yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}:no")],
    ])

def admin_actions(app_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Одобрить", callback_data=f"approve:{app_id}"),
            InlineKeyboardButton(text="🔴 Отказать", callback_data=f"reject:{app_id}"),
        ],
        [InlineKeyboardButton(text="💸 Выдано", callback_data=f"paid:{app_id}")],
    ])
