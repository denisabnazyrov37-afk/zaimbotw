import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from app.config import settings
from app.models import LoanApplication

def _font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont("AppFont", path))
            return "AppFont"
    return "Helvetica"

def create_contract(app: LoanApplication) -> str:
    os.makedirs(settings.contract_dir, exist_ok=True)
    path = os.path.join(settings.contract_dir, f"contract_{app.id}.pdf")
    font = _font()

    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    c.setFont(font, 12)
    y = height - 60

    lines = [
        f"{settings.company_name}",
        "ПРОЕКТ ДОГОВОРА ЗАЙМА",
        "",
        f"Номер заявки: {app.id}",
        f"Дата формирования: {app.created_at:%d.%m.%Y}",
        "",
        f"Заемщик: {app.full_name}",
        f"Дата рождения: {app.birth_date}",
        f"Сумма займа: {app.amount}",
        f"Срок: {app.term_months} месяцев",
        f"Банк/реквизиты: {app.bank_details}",
        "",
        "Документ является проектом договора и требует юридической проверки",
        "перед использованием. Условия займа должны соответствовать",
        "фактически согласованным сторонами условиям и применимому праву.",
    ]

    for line in lines:
        c.drawString(50, y, line[:110])
        y -= 20
        if y < 60:
            c.showPage()
            c.setFont(font, 12)
            y = height - 60

    c.save()
    return path
