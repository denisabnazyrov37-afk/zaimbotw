import os
import re
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import LoanApplication
from app.states import LoanForm
from app.keyboards import main_kb, yes_no, admin_actions
from app.notifications import notify_new_application
from app.pdf import create_contract

router = Router()

STATUS = {
    "review": "🟡 На рассмотрении",
    "approved": "🟢 Одобрено",
    "rejected": "🔴 Отказано",
    "paid": "💸 Выдано",
}

def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids

@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Добро пожаловать.\n\n"
        "Бот позволяет подать заявку на займ и отслеживать ее статус.",
        reply_markup=main_kb(),
    )

@router.message(F.text == "📝 Подать заявку")
async def begin(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(LoanForm.full_name)
    await message.answer("Введите ФИО:")

@router.message(LoanForm.full_name)
async def full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await state.set_state(LoanForm.phone)
    await message.answer("Введите номер телефона:")

@router.message(LoanForm.phone)
async def phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await state.set_state(LoanForm.birth_date)
    await message.answer("Введите дату рождения в формате ДД.ММ.ГГГГ:")

@router.message(LoanForm.birth_date)
async def birth_date(message: Message, state: FSMContext):
    await state.update_data(birth_date=message.text.strip())
    await state.set_state(LoanForm.address)
    await message.answer("Введите адрес фактического проживания:")

@router.message(LoanForm.address)
async def address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await state.set_state(LoanForm.passport_data)
    await message.answer("Введите паспортные данные:")

@router.message(LoanForm.passport_data)
async def passport(message: Message, state: FSMContext):
    await state.update_data(passport_data=message.text.strip())
    await state.set_state(LoanForm.registration_address)
    await message.answer("Введите адрес регистрации:")

@router.message(LoanForm.registration_address)
async def registration(message: Message, state: FSMContext):
    await state.update_data(registration_address=message.text.strip())
    await state.set_state(LoanForm.amount)
    await message.answer("Введите сумму займа в рублях:")

@router.message(LoanForm.amount)
async def amount(message: Message, state: FSMContext):
    try:
        value = int(message.text.replace(" ", "").replace(",", ""))
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное целое число, например: 100000")
        return
    await state.update_data(amount=value)
    await state.set_state(LoanForm.term_months)
    await message.answer("Введите срок займа в месяцах:")

@router.message(LoanForm.term_months)
async def term(message: Message, state: FSMContext):
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите срок целым числом месяцев, например: 12")
        return
    await state.update_data(term_months=value)
    await state.set_state(LoanForm.bank_details)
    await message.answer("Введите название банка и реквизиты для выдачи займа:")

@router.message(LoanForm.bank_details)
async def bank(message: Message, state: FSMContext):
    await state.update_data(bank_details=message.text.strip())
    await state.set_state(LoanForm.passport_photo)
    await message.answer("Отправьте фото/скан паспорта одним изображением:")

async def save_photo(message: Message, state: FSMContext, key: str):
    if not message.photo:
        await message.answer("Пожалуйста, отправьте именно фотографию.")
        return
    photo = message.photo[-1]
    folder = os.path.join(settings.upload_dir, str(message.from_user.id))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{key}_{photo.file_id}.jpg")
    await message.bot.download(photo, destination=path)
    await state.update_data(**{key: path})

@router.message(LoanForm.passport_photo)
async def passport_photo(message: Message, state: FSMContext):
    await save_photo(message, state, "passport_photo")
    await state.set_state(LoanForm.registration_photo)
    await message.answer("Отправьте фото документа, подтверждающего регистрацию:")

@router.message(LoanForm.registration_photo)
async def registration_photo(message: Message, state: FSMContext):
    await save_photo(message, state, "registration_photo")
    await state.set_state(LoanForm.selfie_photo)
    await message.answer("Отправьте селфи, на котором вы держите паспорт рядом с лицом:")

@router.message(LoanForm.selfie_photo)
async def selfie_photo(message: Message, state: FSMContext):
    await save_photo(message, state, "selfie_photo")
    await state.set_state(LoanForm.personal_confirm)
    await message.answer(
        "Подтвердите, что вы согласны на обработку предоставленных персональных данных "
        "для рассмотрения заявки.",
        reply_markup=yes_no("personal"),
    )

@router.callback_query(F.data.startswith("personal:"))
async def personal_confirm(call: CallbackQuery, state: FSMContext):
    if call.data.endswith(":no"):
        await state.clear()
        await call.message.edit_text("Заявка отменена.")
        return

    await state.update_data(personal_data_confirmed=True)
    data = await state.get_data()
    summary = (
        "Проверьте данные заявки:\n\n"
        f"ФИО: {data['full_name']}\n"
        f"Телефон: {data['phone']}\n"
        f"Дата рождения: {data['birth_date']}\n"
        f"Адрес: {data['address']}\n"
        f"Паспорт: {data['passport_data']}\n"
        f"Регистрация: {data['registration_address']}\n"
        f"Сумма: {data['amount']}\n"
        f"Срок: {data['term_months']} мес.\n"
        f"Банк/реквизиты: {data['bank_details']}\n\n"
        "Подтвердить отправку заявки?"
    )
    await state.set_state(LoanForm.final_confirm)
    await call.message.edit_text(summary, reply_markup=yes_no("final"))
    await call.answer()

@router.callback_query(F.data.startswith("final:"))
async def final_confirm(call: CallbackQuery, state: FSMContext):
    if call.data.endswith(":no"):
        await state.clear()
        await call.message.edit_text("Заявка не отправлена.")
        return

    data = await state.get_data()
    async with SessionLocal() as session:
        app = LoanApplication(
            telegram_user_id=call.from_user.id,
            telegram_username=call.from_user.username,
            full_name=data["full_name"],
            phone=data["phone"],
            birth_date=data["birth_date"],
            address=data["address"],
            passport_data=data["passport_data"],
            registration_address=data["registration_address"],
            amount=data["amount"],
            term_months=data["term_months"],
            bank_details=data["bank_details"],
            passport_photo=data.get("passport_photo"),
            registration_photo=data.get("registration_photo"),
            selfie_photo=data.get("selfie_photo"),
            personal_data_confirmed=True,
            final_confirmed=True,
            status="review",
        )
        session.add(app)
        await session.commit()
        await session.refresh(app)

    await state.clear()
    await notify_new_application(call.bot, app)
    await call.message.edit_text(
        f"✅ Заявка #{app.id} принята.\n"
        "Статус: 🟡 На рассмотрении."
    )
    await call.answer()

@router.message(F.text == "📋 Мои заявки")
async def my_apps(message: Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(LoanApplication)
            .where(LoanApplication.telegram_user_id == message.from_user.id)
            .order_by(LoanApplication.id.desc())
        )
        apps = result.scalars().all()

    if not apps:
        await message.answer("У вас пока нет заявок.")
        return

    lines = ["📋 Ваши заявки:"]
    for a in apps:
        lines.append(
            f"#{a.id} — {STATUS.get(a.status, a.status)} — "
            f"{a.amount} руб. — {a.term_months} мес."
        )
    await message.answer("\n".join(lines))

@router.message(Command("contract"))
async def contract(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer("Использование: /contract_ID")
        return
    app_id = int(command.args)
    async with SessionLocal() as session:
        app = await session.get(LoanApplication, app_id)
    if not app or app.telegram_user_id != message.from_user.id:
        await message.answer("Заявка не найдена.")
        return
    if app.status not in ("approved", "paid"):
        await message.answer("Договор доступен после одобрения заявки.")
        return

    path = app.contract_path or create_contract(app)
    if not app.contract_path:
        async with SessionLocal() as session:
            dbapp = await session.get(LoanApplication, app.id)
            dbapp.contract_path = path
            await session.commit()

    await message.answer_document(FSInputFile(path), caption=f"Проект договора по заявке #{app.id}")

@router.message(Command("admin"))
async def admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    async with SessionLocal() as session:
        result = await session.execute(
            select(LoanApplication).order_by(LoanApplication.id.desc()).limit(50)
        )
        apps = result.scalars().all()

    if not apps:
        await message.answer("Заявок нет.")
        return

    for a in apps:
        text = (
            f"Заявка #{a.id}\n"
            f"ФИО: {a.full_name}\n"
            f"Сумма: {a.amount}\n"
            f"Срок: {a.term_months} мес.\n"
            f"Статус: {STATUS.get(a.status, a.status)}"
        )
        await message.answer(text, reply_markup=admin_actions(a.id))

async def set_status(call: CallbackQuery, app_id: int, status: str):
    async with SessionLocal() as session:
        app = await session.get(LoanApplication, app_id)
        if not app:
            await call.answer("Заявка не найдена", show_alert=True)
            return
        app.status = status
        if status == "approved":
            app.contract_path = create_contract(app)
        if status == "paid":
            app.paid_at = datetime.utcnow()
        await session.commit()

    await call.message.answer(
        f"Заявка #{app_id}: {STATUS[status]}"
    )
    # Уведомление заемщику
    try:
        await call.bot.send_message(
            app.telegram_user_id,
            f"По заявке #{app_id} изменен статус: {STATUS[status]}"
            + (f"\nДоговор: /contract {app_id}" if status == "approved" else "")
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("approve:"))
async def approve_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await set_status(call, int(call.data.split(":")[1]), "approved")
    await call.answer("Одобрено")

@router.callback_query(F.data.startswith("reject:"))
async def reject_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await set_status(call, int(call.data.split(":")[1]), "rejected")
    await call.answer("Отказано")

@router.callback_query(F.data.startswith("paid:"))
async def paid_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await set_status(call, int(call.data.split(":")[1]), "paid")
    await call.answer("Выдача отмечена")


@router.message(F.text.regexp(r"^/(approve|reject|paid|case)_\d+$"))
async def underscore_commands(message: Message):
    if not is_admin(message.from_user.id):
        return
    m = re.match(r"^/(approve|reject|paid|case)_(\d+)$", message.text or "")
    if not m:
        return
    action, app_id_s = m.groups()
    app_id = int(app_id_s)

    if action == "case":
        # Reuse the normal case command logic.
        async with SessionLocal() as session:
            app = await session.get(LoanApplication, app_id)
        if not app:
            await message.answer("Заявка не найдена.")
            return
        await message.answer(
            f"📄 Техническая выписка #{app.id}\n\n"
            f"user_id: {app.telegram_user_id}\n"
            f"username: @{app.telegram_username or '-'}\n"
            f"created_at: {app.created_at}\n"
            f"status: {app.status}\n"
            f"full_name: {app.full_name}\n"
            f"phone: {app.phone}\n"
            f"birth_date: {app.birth_date}\n"
            f"amount: {app.amount}\n"
            f"term_months: {app.term_months}\n"
            f"personal_confirmed: {app.personal_data_confirmed}\n"
            f"final_confirmed: {app.final_confirmed}\n"
            f"passport_file: {bool(app.passport_photo)}\n"
            f"registration_file: {bool(app.registration_photo)}\n"
            f"selfie_file: {bool(app.selfie_photo)}\n"
            f"contract: {app.contract_path or '-'}"
        )
        return

    await _status_command(message, app_id, {
        "approve": "approved",
        "reject": "rejected",
        "paid": "paid",
    }[action])

@router.message(Command("approve"))
async def approve_cmd(message: Message, command: CommandObject):
    if is_admin(message.from_user.id) and command.args and command.args.isdigit():
        await _status_command(message, int(command.args), "approved")

@router.message(Command("reject"))
async def reject_cmd(message: Message, command: CommandObject):
    if is_admin(message.from_user.id) and command.args and command.args.isdigit():
        await _status_command(message, int(command.args), "rejected")

@router.message(Command("paid"))
async def paid_cmd(message: Message, command: CommandObject):
    if is_admin(message.from_user.id) and command.args and command.args.isdigit():
        await _status_command(message, int(command.args), "paid")

async def _status_command(message: Message, app_id: int, status: str):
    async with SessionLocal() as session:
        app = await session.get(LoanApplication, app_id)
        if not app:
            await message.answer("Заявка не найдена.")
            return
        app.status = status
        if status == "approved":
            app.contract_path = create_contract(app)
        if status == "paid":
            app.paid_at = datetime.utcnow()
        await session.commit()
    await message.answer(f"Заявка #{app_id}: {STATUS[status]}")

@router.message(Command("case"))
async def case_cmd(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args or not command.args.isdigit():
        await message.answer("Использование: /case ID")
        return

    app_id = int(command.args)
    async with SessionLocal() as session:
        app = await session.get(LoanApplication, app_id)
    if not app:
        await message.answer("Заявка не найдена.")
        return

    text = (
        f"📄 Техническая выписка #{app.id}\n\n"
        f"user_id: {app.telegram_user_id}\n"
        f"username: @{app.telegram_username or '-'}\n"
        f"created_at: {app.created_at}\n"
        f"status: {app.status}\n"
        f"full_name: {app.full_name}\n"
        f"phone: {app.phone}\n"
        f"birth_date: {app.birth_date}\n"
        f"amount: {app.amount}\n"
        f"term_months: {app.term_months}\n"
        f"personal_confirmed: {app.personal_data_confirmed}\n"
        f"final_confirmed: {app.final_confirmed}\n"
        f"passport_file: {bool(app.passport_photo)}\n"
        f"registration_file: {bool(app.registration_photo)}\n"
        f"selfie_file: {bool(app.selfie_photo)}\n"
        f"contract: {app.contract_path or '-'}"
    )
    await message.answer(text)
