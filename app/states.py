from aiogram.fsm.state import State, StatesGroup

class LoanForm(StatesGroup):
    full_name = State()
    phone = State()
    birth_date = State()
    address = State()
    passport_data = State()
    registration_address = State()
    amount = State()
    term_months = State()
    bank_details = State()
    passport_photo = State()
    registration_photo = State()
    selfie_photo = State()
    personal_confirm = State()
    final_confirm = State()
