
import os, sqlite3, threading, secrets, hashlib, hmac, json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl
from flask import Flask, request, jsonify, send_from_directory
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters

# ============================================================
# НАСТРОЙКИ — ВСТАВЬ СЮДА ТОКЕН И TELEGRAM ID АДМИНА
# ============================================================
BOT_TOKEN = "8972994110:AAEnae91uH3w57YZnqLvpU-LLe2SkyBsRCM"
ADMIN_IDS = {"5930286295"}

# После публикации на Render укажи адрес сервиса:
MINI_APP_URL = "https://YOUR-SERVICE.onrender.com/"
# ============================================================

DB_PATH = Path(__file__).with_name("loan.db")
FILES_DIR = Path(__file__).with_name("case_files")
FILES_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder="web", static_url_path="")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id TEXT NOT NULL, username TEXT DEFAULT '',
        first_name TEXT NOT NULL, last_name TEXT NOT NULL, patronymic TEXT DEFAULT '',
        phone TEXT NOT NULL, birth_date TEXT DEFAULT '', address TEXT DEFAULT '',
        passport_series TEXT NOT NULL, passport_number TEXT NOT NULL,
        passport_date TEXT NOT NULL, passport_department TEXT NOT NULL,
        passport_issued_by TEXT NOT NULL, registration_address TEXT NOT NULL,
        amount INTEGER NOT NULL, term_days INTEGER NOT NULL,
        bank TEXT NOT NULL, account TEXT NOT NULL, bik TEXT DEFAULT '',
        recipient_name TEXT NOT NULL,
        passport_front_file_id TEXT DEFAULT '', passport_registration_file_id TEXT DEFAULT '',
        selfie_file_id TEXT DEFAULT '',
        person_confirmed_at TEXT DEFAULT '', final_confirmed_at TEXT DEFAULT '',
        approved_at TEXT DEFAULT '', paid_at TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, application_id INTEGER NOT NULL,
        actor_telegram_id TEXT NOT NULL, action TEXT NOT NULL,
        created_at TEXT NOT NULL, details TEXT DEFAULT ''
    )""")
    conn.commit(); conn.close()

def audit(app_id, actor, action, details=""):
    conn=db()
    conn.execute("INSERT INTO audit_log(application_id,actor_telegram_id,action,created_at,details) VALUES(?,?,?,?,?)",
                 (app_id,str(actor),action,now_iso(),details))
    conn.commit(); conn.close()

def verify_webapp_data(init_data: str):
    """Validate Telegram Mini App initData using the bot token."""
    if not init_data or not BOT_TOKEN or BOT_TOKEN.startswith("ВСТАВЬ_"):
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k,v in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, received_hash):
            return None
        # Reject stale initData older than 24h.
        auth_date = int(pairs.get("auth_date","0"))
        if abs(datetime.now(timezone.utc).timestamp() - auth_date) > 86400:
            return None
        user = json.loads(pairs.get("user","{}"))
        return user
    except Exception:
        return None

def user_from_request():
    init_data = request.headers.get("X-Telegram-Init-Data","")
    return verify_webapp_data(init_data)

def fmt_money(n): return f"{int(n):,}".replace(",", " ") + " ₽"

def contract_pdf(row, out_path):
    # ReportLab built-in DejaVu may not be available everywhere; use a system font if present.
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if os.path.exists(font):
        pdfmetrics.registerFont(TTFont("DV", font))
        pdfmetrics.registerFont(TTFont("DV-Bold", bold))
        normal, strong = "DV", "DV-Bold"
    else:
        normal = strong = "Helvetica"

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=42)
    styles=getSampleStyleSheet()
    title=ParagraphStyle("title", parent=styles["Title"], fontName=strong, fontSize=18, leading=23, alignment=TA_CENTER, spaceAfter=18)
    h=ParagraphStyle("h", parent=styles["Heading2"], fontName=strong, fontSize=12, leading=16, spaceBefore=10, spaceAfter=6)
    body=ParagraphStyle("body", parent=styles["BodyText"], fontName=normal, fontSize=9.5, leading=14, spaceAfter=6)
    small=ParagraphStyle("small", parent=body, fontSize=8, leading=11)

    story=[Paragraph("ПРОЕКТ ДОГОВОРА ЗАЙМА", title),
           Paragraph(f"Договор № {row['id']}", body),
           Paragraph(f"Дата формирования: {now_iso()[:19].replace('T',' ')} UTC", small),
           Spacer(1,8)]
    story += [Paragraph("1. Стороны", h)]
    borrower=f"{row['last_name']} {row['first_name']} {row['patronymic'] or ''}".strip()
    party_data=[
        ["Заемщик", borrower],
        ["Дата рождения", row["birth_date"]],
        ["Паспорт", f"{row['passport_series']} {row['passport_number']}"],
        ["Дата выдачи", row["passport_date"]],
        ["Код подразделения", row["passport_department"]],
        ["Кем выдан", row["passport_issued_by"]],
        ["Адрес регистрации", row["registration_address"]],
        ["Телефон", row["phone"]],
    ]
    t=Table([[Paragraph(str(a),small),Paragraph(str(b),small)] for a,b in party_data], colWidths=[150,330])
    t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP"),("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
    story += [t, Paragraph("2. Предмет договора", h),
              Paragraph(f"Займодавец предоставляет Заемщику денежные средства в размере <b>{fmt_money(row['amount'])}</b>. Срок займа — <b>{row['term_days']} календарных дней</b> с даты фактической передачи денежных средств.", body),
              Paragraph("3. Порядок передачи и возврата", h),
              Paragraph("Факт передачи денежных средств должен подтверждаться банковской операцией/иным документом, позволяющим установить сумму, дату и стороны операции. Условия возврата, проценты, неустойка и иные платежи должны быть определены сторонами до подписания договора.", body),
              Paragraph("4. Электронное подтверждение", h),
              Paragraph(f"Заявка сформирована в Telegram. В системе зафиксировано подтверждение личных данных: {row['person_confirmed_at'] or '—'}, финальное подтверждение заявки: {row['final_confirmed_at'] or '—'}. Эти отметки являются техническими записями системы и сами по себе не заменяют юридическую проверку способа заключения договора.", body),
              Paragraph("5. Реквизиты для перечисления", h)]
    bank_data=[["Банк",row["bank"]],["Счет/карта",row["account"]],["БИК",row["bik"] or "—"],["Получатель",row["recipient_name"]]]
    t2=Table([[Paragraph(str(a),small),Paragraph(str(b),small)] for a,b in bank_data], colWidths=[150,330])
    t2.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP"),("BACKGROUND",(0,0),(0,-1),colors.whitesmoke)]))
    story += [t2, Paragraph("6. Заключительные положения", h),
              Paragraph("Перед использованием документа стороны должны проверить применимое законодательство, условия займа, проценты и порядок подписания. Настоящий файл в этой версии проекта является шаблоном/проектом и не является юридическим заключением.", body),
              Spacer(1,18),
              Paragraph("Заемщик: ________________________________", body),
              Paragraph("Займодавец: ______________________________", body)]
    doc.build(story)

@app.route("/")
def index():
    return send_from_directory("web","index.html")

@app.route("/health")
def health():
    return jsonify(ok=True)

@app.route("/api/applications", methods=["GET"])
def my_apps():
    user=user_from_request()
    if not user: return jsonify(error="Недействительная Telegram-сессия"),401
    conn=db()
    rows=conn.execute("SELECT id,amount,term_days,status,created_at,approved_at,paid_at FROM applications WHERE telegram_id=? ORDER BY id DESC",
                      (str(user.get("id")),)).fetchall()
    conn.close()
    return jsonify(applications=[dict(r) for r in rows])

@app.route("/api/application/<int:app_id>/contract", methods=["GET"])
def get_contract(app_id):
    user=user_from_request()
    if not user: return jsonify(error="Недействительная Telegram-сессия"),401
    conn=db(); row=conn.execute("SELECT * FROM applications WHERE id=?",(app_id,)).fetchone(); conn.close()
    if not row or str(row["telegram_id"]) != str(user.get("id")): return jsonify(error="Нет доступа"),403
    path=FILES_DIR/f"contract_{app_id}.pdf"
    if not path.exists(): contract_pdf(row,path)
    return send_from_directory(FILES_DIR, path.name, as_attachment=True)

@app.route("/api/submit", methods=["POST"])
def submit():
    user=user_from_request()
    if not user: return jsonify(error="Недействительная Telegram-сессия"),401
    data=request.form
    required=["first_name","last_name","phone","birth_date","address","passport_series","passport_number",
              "passport_date","passport_department","passport_issued_by","registration_address",
              "amount","term_days","bank","account","recipient_name"]
    missing=[x for x in required if not data.get(x)]
    if missing: return jsonify(error="Не заполнены поля: "+", ".join(missing)),400
    try:
        amount=int(data["amount"]); term=int(data["term_days"])
        if amount<=0 or term<=0: raise ValueError
    except: return jsonify(error="Некорректная сумма или срок"),400

    now=now_iso()
    conn=db()
    cur=conn.execute("""INSERT INTO applications
    (telegram_id,username,first_name,last_name,patronymic,phone,birth_date,address,
     passport_series,passport_number,passport_date,passport_department,passport_issued_by,
     registration_address,amount,term_days,bank,account,bik,recipient_name,
     person_confirmed_at,final_confirmed_at,status,created_at,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (str(user["id"]),user.get("username",""),data["first_name"],data["last_name"],data.get("patronymic",""),
     data["phone"],data["birth_date"],data["address"],data["passport_series"],data["passport_number"],
     data["passport_date"],data["passport_department"],data["passport_issued_by"],data["registration_address"],
     amount,term,data["bank"],data["account"],data.get("bik",""),data["recipient_name"],now,now,"pending",now,now))
    app_id=cur.lastrowid; conn.commit()
    row=conn.execute("SELECT * FROM applications WHERE id=?",(app_id,)).fetchone()
    conn.close()
    audit(app_id,user["id"],"miniapp_submitted","Заявка отправлена через Mini App")
    path=FILES_DIR/f"contract_{app_id}.pdf"; contract_pdf(row,path)
    return jsonify(ok=True,application_id=app_id)

# ---------- Telegram bot ----------
def main_keyboard():
    rows=[]
    if MINI_APP_URL and "YOUR-SERVICE" not in MINI_APP_URL:
        rows.append([KeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url=MINI_APP_URL))])
    rows += [["📝 Подать заявку"],["📋 Мои заявки","👤 Мой профиль"],["ℹ️ Помощь"]]
    return ReplyKeyboardMarkup(rows,resize_keyboard=True)

async def start(update, context):
    await update.message.reply_text(
        "👋 Добро пожаловать!\n\n"
        "🚀 Открыть приложение — удобная анкета внутри Telegram.\n"
        "Там можно заполнить данные и отправить заявку.\n\n"
        "Если Mini App ещё не настроен, используйте «📝 Подать заявку».",
        reply_markup=main_keyboard())

async def help_cmd(update,context):
    await update.message.reply_text("ℹ️ Заполните заявку в боте или Mini App. После отправки система создаёт технический проект договора.",reply_markup=main_keyboard())

async def my_apps_bot(update,context):
    conn=db(); rows=conn.execute("SELECT id,amount,term_days,status,created_at FROM applications WHERE telegram_id=? ORDER BY id DESC",(str(update.effective_user.id),)).fetchall(); conn.close()
    labels={"pending":"🟡 На рассмотрении","approved":"🟢 Одобрена","rejected":"🔴 Отказана","paid":"💸 Выдана"}
    if not rows: return await update.message.reply_text("Заявок пока нет.",reply_markup=main_keyboard())
    for r in rows:
        await update.message.reply_text(f"📋 Заявка №{r['id']}\n💰 {fmt_money(r['amount'])}\n📅 {r['term_days']} дней\n📌 {labels.get(r['status'],r['status'])}\n📄 /contract_{r['id']}")

async def contract_cmd(update,context):
    try: app_id=int(update.message.text.split("_",1)[1])
    except: return
    conn=db(); row=conn.execute("SELECT * FROM applications WHERE id=?",(app_id,)).fetchone(); conn.close()
    if not row or str(row["telegram_id"]) != str(update.effective_user.id):
        return await update.message.reply_text("Договор не найден.")
    path=FILES_DIR/f"contract_{app_id}.pdf"
    contract_pdf(row,path)
    await update.message.reply_document(document=str(path),caption=f"📄 Проект договора по заявке №{app_id}")

async def admin(update,context):
    if str(update.effective_user.id) not in ADMIN_IDS: return await update.message.reply_text("Нет доступа.")
    conn=db(); rows=conn.execute("SELECT id,last_name,first_name,amount,term_days,status,created_at FROM applications ORDER BY id DESC LIMIT 30").fetchall(); conn.close()
    if not rows: return await update.message.reply_text("Заявок нет.")
    for r in rows:
        await update.message.reply_text(f"№{r['id']} — {r['last_name']} {r['first_name']}\n{fmt_money(r['amount'])} / {r['term_days']} дней\nСтатус: {r['status']}\n/approve_{r['id']} /reject_{r['id']} /paid_{r['id']} /case_{r['id']}")

async def admin_action(update,context):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    txt=update.message.text
    try: app_id=int(txt.rsplit("_",1)[1])
    except: return
    now=now_iso()
    conn=db(); row=conn.execute("SELECT * FROM applications WHERE id=?",(app_id,)).fetchone()
    if not row: conn.close(); return await update.message.reply_text("Заявка не найдена.")
    if txt.startswith("/approve_"):
        status="approved"; conn.execute("UPDATE applications SET status=?,approved_at=?,updated_at=? WHERE id=?",(status,now,now,app_id)); msg="🟢 Заявка одобрена."
    elif txt.startswith("/reject_"):
        status="rejected"; conn.execute("UPDATE applications SET status=?,updated_at=? WHERE id=?",(status,now,app_id)); msg="🔴 Заявка отклонена."
    else:
        status="paid"; conn.execute("UPDATE applications SET status=?,paid_at=?,updated_at=? WHERE id=?",(status,now,now,app_id)); msg="💸 Выдача отмечена."
    conn.commit(); row=conn.execute("SELECT * FROM applications WHERE id=?",(app_id,)).fetchone(); conn.close()
    audit(app_id,update.effective_user.id,status,msg)
    if status in ("approved","paid"):
        path=FILES_DIR/f"contract_{app_id}.pdf"; contract_pdf(row,path)
    await update.message.reply_text(msg)
    try:
        await context.bot.send_message(chat_id=int(row["telegram_id"]),text=f"Заявка №{app_id}\n{msg}")
        if status=="approved":
            await context.bot.send_document(chat_id=int(row["telegram_id"]),document=str(path),caption="📄 Проект договора займа")
    except Exception as e: print(e)

def run_flask():
    port=int(os.getenv("PORT","10000"))
    app.run(host="0.0.0.0",port=port,debug=False,use_reloader=False)

def run_bot():
    import asyncio
    async def runner():
        if not BOT_TOKEN or BOT_TOKEN.startswith("ВСТАВЬ_"):
            raise RuntimeError("В bot.py не указан BOT_TOKEN")
        init_db()
        application=Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start",start))
        application.add_handler(CommandHandler("help",help_cmd))
        application.add_handler(CommandHandler("admin",admin))
        application.add_handler(MessageHandler(filters.Regex(r"^/contract_\d+$"),contract_cmd))
        application.add_handler(MessageHandler(filters.Regex(r"^/(approve|reject|paid)_\d+$"),admin_action))
        application.add_handler(MessageHandler(filters.Regex("^📋 Мои заявки$"),my_apps_bot))
        application.add_handler(MessageHandler(filters.Regex("^ℹ️ Помощь$"),help_cmd))
        application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=[])
    asyncio.run(runner())

if __name__=="__main__":
    init_db()
    t=threading.Thread(target=run_bot,daemon=True)
    t.start()
    run_flask()
