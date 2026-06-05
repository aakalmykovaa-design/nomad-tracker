import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nomad_tracker.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Profile(Base):
    __tablename__ = "profiles"
    id = Column(String, primary_key=True, default="default")
    citizenship = Column(String, default="RU")
    citizenship_label = Column(String, default="Россия")
    current_country = Column(String, default="")
    topics = Column(String, default="visa,residency,nomad_visa,tax,banking")
    updated_at = Column(DateTime, default=datetime.utcnow)


class TrackedCountry(Base):
    __tablename__ = "tracked_countries"
    code = Column(String(5), primary_key=True)
    name = Column(String, nullable=False)
    flag = Column(String(5))
    region = Column(String)
    is_active = Column(Boolean, default=True)
    last_status = Column(Text, default="Ещё не проверялось")
    last_severity = Column(String, default="unknown")
    last_check = Column(DateTime)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    country_code = Column(String(5))
    country_name = Column(String)
    title = Column(String)
    summary = Column(Text)
    severity = Column(String, default="info")
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_telegram = Column(Boolean, default=False)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text, default="")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DEFAULT_COUNTRIES = [
    {"code": "PT", "name": "Португалия", "flag": "🇵🇹", "region": "ЕС"},
    {"code": "DE", "name": "Германия", "flag": "🇩🇪", "region": "ЕС"},
    {"code": "ES", "name": "Испания", "flag": "🇪🇸", "region": "ЕС"},
    {"code": "CY", "name": "Кипр", "flag": "🇨🇾", "region": "ЕС"},
    {"code": "RS", "name": "Сербия", "flag": "🇷🇸", "region": "Балканы"},
    {"code": "ME", "name": "Черногория", "flag": "🇲🇪", "region": "Балканы"},
    {"code": "GE", "name": "Грузия", "flag": "🇬🇪", "region": "СНГ"},
    {"code": "AM", "name": "Армения", "flag": "🇦🇲", "region": "СНГ"},
    {"code": "TH", "name": "Таиланд", "flag": "🇹🇭", "region": "Азия"},
    {"code": "ID", "name": "Индонезия (Бали)", "flag": "🇮🇩", "region": "Азия"},
    {"code": "TR", "name": "Турция", "flag": "🇹🇷", "region": "Другое"},
]


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(Profile).first():
            db.add(Profile(id="default"))
        for c in DEFAULT_COUNTRIES:
            if not db.query(TrackedCountry).filter_by(code=c["code"]).first():
                db.add(TrackedCountry(**c))
        for key in ["telegram_chat_id", "check_interval_hours"]:
            if not db.query(Setting).filter_by(key=key).first():
                db.add(Setting(key=key, value="12" if key == "check_interval_hours" else ""))
        db.commit()
    finally:
        db.close()
