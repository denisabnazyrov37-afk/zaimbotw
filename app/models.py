from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(64))
    birth_date: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(Text)
    passport_data: Mapped[str] = mapped_column(Text)
    registration_address: Mapped[str] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(Integer)
    term_months: Mapped[int] = mapped_column(Integer)
    bank_details: Mapped[str] = mapped_column(Text)

    passport_photo: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_photo: Mapped[str | None] = mapped_column(Text, nullable=True)
    selfie_photo: Mapped[str | None] = mapped_column(Text, nullable=True)

    personal_data_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    final_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(32), default="review")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract_path: Mapped[str | None] = mapped_column(Text, nullable=True)
