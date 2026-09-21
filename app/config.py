import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def csv_ints(value: str) -> set[int]:
    return {int(x.strip()) for x in value.split(",") if x.strip()}

@dataclass
class Settings:
    bot_token: str
    database_url: str
    notify_chat_id: int | None
    admin_ids: set[int]
    company_name: str
    company_inn: str
    company_address: str
    upload_dir: str
    contract_dir: str

settings = Settings(
    bot_token=os.environ["BOT_TOKEN"],
    database_url=os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://loanbot:loanbot@localhost:5432/loanbot",
    ),
    notify_chat_id=int(os.environ["NOTIFY_CHAT_ID"]) if os.getenv("NOTIFY_CHAT_ID") else None,
    admin_ids=csv_ints(os.getenv("ADMIN_IDS", "")),
    company_name=os.getenv("COMPANY_NAME", "Ваша организация"),
    company_inn=os.getenv("COMPANY_INN", ""),
    company_address=os.getenv("COMPANY_ADDRESS", ""),
    upload_dir=os.getenv("UPLOAD_DIR", "./data/uploads"),
    contract_dir=os.getenv("CONTRACT_DIR", "./data/contracts"),
)
