import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, text
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
    goals = Column(String, default="nomad")           # nomad / relocation / retirement / investment
    budget = Column(String, default="")               # <1000 / 1000-2000 / 2000-3500 / 3500+
    languages = Column(String, default="")            # через запятую
    extra_citizenships = Column(String, default="")   # через запятую, например "AM,GE"


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
    custom_topics = Column(String, default="")  # если пустая — используются темы профиля


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


COUNTRY_CATALOG = [
    # ЕС
    {"code": "PT", "name": "Португалия",    "flag": "🇵🇹", "region": "ЕС"},
    {"code": "ES", "name": "Испания",       "flag": "🇪🇸", "region": "ЕС"},
    {"code": "DE", "name": "Германия",      "flag": "🇩🇪", "region": "ЕС"},
    {"code": "FR", "name": "Франция",       "flag": "🇫🇷", "region": "ЕС"},
    {"code": "IT", "name": "Италия",        "flag": "🇮🇹", "region": "ЕС"},
    {"code": "NL", "name": "Нидерланды",    "flag": "🇳🇱", "region": "ЕС"},
    {"code": "AT", "name": "Австрия",       "flag": "🇦🇹", "region": "ЕС"},
    {"code": "CZ", "name": "Чехия",         "flag": "🇨🇿", "region": "ЕС"},
    {"code": "PL", "name": "Польша",        "flag": "🇵🇱", "region": "ЕС"},
    {"code": "GR", "name": "Греция",        "flag": "🇬🇷", "region": "ЕС"},
    {"code": "CY", "name": "Кипр",          "flag": "🇨🇾", "region": "ЕС"},
    {"code": "MT", "name": "Мальта",        "flag": "🇲🇹", "region": "ЕС"},
    {"code": "IE", "name": "Ирландия",      "flag": "🇮🇪", "region": "ЕС"},
    {"code": "EE", "name": "Эстония",       "flag": "🇪🇪", "region": "ЕС"},
    {"code": "LV", "name": "Латвия",        "flag": "🇱🇻", "region": "ЕС"},
    {"code": "LT", "name": "Литва",         "flag": "🇱🇹", "region": "ЕС"},
    {"code": "HU", "name": "Венгрия",       "flag": "🇭🇺", "region": "ЕС"},
    {"code": "RO", "name": "Румыния",       "flag": "🇷🇴", "region": "ЕС"},
    {"code": "BG", "name": "Болгария",      "flag": "🇧🇬", "region": "ЕС"},
    {"code": "CH", "name": "Швейцария",     "flag": "🇨🇭", "region": "ЕС"},
    # Балканы
    {"code": "RS", "name": "Сербия",        "flag": "🇷🇸", "region": "Балканы"},
    {"code": "ME", "name": "Черногория",    "flag": "🇲🇪", "region": "Балканы"},
    {"code": "MK", "name": "Македония",     "flag": "🇲🇰", "region": "Балканы"},
    {"code": "AL", "name": "Албания",       "flag": "🇦🇱", "region": "Балканы"},
    {"code": "BA", "name": "Босния",        "flag": "🇧🇦", "region": "Балканы"},
    {"code": "HR", "name": "Хорватия",      "flag": "🇭🇷", "region": "Балканы"},
    # СНГ
    {"code": "GE", "name": "Грузия",        "flag": "🇬🇪", "region": "СНГ"},
    {"code": "AM", "name": "Армения",       "flag": "🇦🇲", "region": "СНГ"},
    {"code": "AZ", "name": "Азербайджан",   "flag": "🇦🇿", "region": "СНГ"},
    {"code": "KZ", "name": "Казахстан",     "flag": "🇰🇿", "region": "СНГ"},
    {"code": "KG", "name": "Кыргызстан",    "flag": "🇰🇬", "region": "СНГ"},
    {"code": "UZ", "name": "Узбекистан",    "flag": "🇺🇿", "region": "СНГ"},
    # Ближний Восток
    {"code": "TR", "name": "Турция",        "flag": "🇹🇷", "region": "Ближний Восток"},
    {"code": "AE", "name": "ОАЭ",           "flag": "🇦🇪", "region": "Ближний Восток"},
    {"code": "IL", "name": "Израиль",       "flag": "🇮🇱", "region": "Ближний Восток"},
    {"code": "QA", "name": "Катар",         "flag": "🇶🇦", "region": "Ближний Восток"},
    {"code": "BH", "name": "Бахрейн",       "flag": "🇧🇭", "region": "Ближний Восток"},
    {"code": "OM", "name": "Оман",          "flag": "🇴🇲", "region": "Ближний Восток"},
    # Азия
    {"code": "TH", "name": "Таиланд",       "flag": "🇹🇭", "region": "Азия"},
    {"code": "ID", "name": "Индонезия (Бали)", "flag": "🇮🇩", "region": "Азия"},
    {"code": "VN", "name": "Вьетнам",       "flag": "🇻🇳", "region": "Азия"},
    {"code": "KH", "name": "Камбоджа",      "flag": "🇰🇭", "region": "Азия"},
    {"code": "PH", "name": "Филиппины",     "flag": "🇵🇭", "region": "Азия"},
    {"code": "MY", "name": "Малайзия",      "flag": "🇲🇾", "region": "Азия"},
    {"code": "SG", "name": "Сингапур",      "flag": "🇸🇬", "region": "Азия"},
    {"code": "JP", "name": "Япония",        "flag": "🇯🇵", "region": "Азия"},
    {"code": "KR", "name": "Южная Корея",   "flag": "🇰🇷", "region": "Азия"},
    {"code": "MM", "name": "Мьянма",        "flag": "🇲🇲", "region": "Азия"},
    {"code": "LK", "name": "Шри-Ланка",     "flag": "🇱🇰", "region": "Азия"},
    {"code": "NP", "name": "Непал",         "flag": "🇳🇵", "region": "Азия"},
    # Америка
    {"code": "US", "name": "США",           "flag": "🇺🇸", "region": "Америка"},
    {"code": "CA", "name": "Канада",        "flag": "🇨🇦", "region": "Америка"},
    {"code": "MX", "name": "Мексика",       "flag": "🇲🇽", "region": "Америка"},
    {"code": "BR", "name": "Бразилия",      "flag": "🇧🇷", "region": "Америка"},
    {"code": "AR", "name": "Аргентина",     "flag": "🇦🇷", "region": "Америка"},
    {"code": "CO", "name": "Колумбия",      "flag": "🇨🇴", "region": "Америка"},
    {"code": "PA", "name": "Панама",        "flag": "🇵🇦", "region": "Америка"},
    {"code": "CR", "name": "Коста-Рика",    "flag": "🇨🇷", "region": "Америка"},
    {"code": "EC", "name": "Эквадор",       "flag": "🇪🇨", "region": "Америка"},
    # Африка / Другое
    {"code": "MA", "name": "Марокко",       "flag": "🇲🇦", "region": "Африка"},
    {"code": "ZA", "name": "ЮАР",           "flag": "🇿🇦", "region": "Африка"},
    {"code": "MU", "name": "Маврикий",      "flag": "🇲🇺", "region": "Африка"},
    {"code": "TZ", "name": "Танзания",      "flag": "🇹🇿", "region": "Африка"},
]

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
    # Добавляем новые колонки если их нет (SQLite совместимо)
    with engine.connect() as conn:
        for sql in [
            "ALTER TABLE tracked_countries ADD COLUMN custom_topics TEXT DEFAULT ''",
            "ALTER TABLE profiles ADD COLUMN goals TEXT DEFAULT 'nomad'",
            "ALTER TABLE profiles ADD COLUMN budget TEXT DEFAULT ''",
            "ALTER TABLE profiles ADD COLUMN languages TEXT DEFAULT ''",
            "ALTER TABLE profiles ADD COLUMN extra_citizenships TEXT DEFAULT ''",
        ]:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
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
