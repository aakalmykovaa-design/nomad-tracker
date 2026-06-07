import os
import uuid
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db, init_db, Profile, TrackedCountry, Alert, Setting, DEFAULT_COUNTRIES, COUNTRY_CATALOG
from checker import check_countries
from telegram_notifier import send_alert, send_test_message
from scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_check():
    from database import SessionLocal
    db = SessionLocal()
    try:
        profile = db.query(Profile).first()
        if not profile:
            return
        countries = db.query(TrackedCountry).filter_by(is_active=True).all()
        if not countries:
            return

        telegram_chat_id = ""
        s = db.query(Setting).filter_by(key="telegram_chat_id").first()
        if s:
            telegram_chat_id = s.value or ""

        profile_dict = {
            "citizenship": profile.citizenship,
            "citizenship_label": profile.citizenship_label,
            "topics": profile.topics,
        }
        country_dicts = [{"code": c.code, "name": c.name, "flag": c.flag} for c in countries]

        logger.info(f"Запуск проверки для {len(country_dicts)} стран...")
        results = check_countries(country_dicts, profile_dict)

        country_map = {c.code: c for c in countries}
        now = datetime.utcnow()

        for r in results:
            code = r.get("code")
            country = country_map.get(code)
            if not country:
                continue

            country.last_status = r.get("status_summary", "")
            country.last_severity = r.get("severity", "ok")
            country.last_check = now

            if r.get("has_changes") and r.get("change_title"):
                alert = Alert(
                    id=str(uuid.uuid4()),
                    country_code=code,
                    country_name=country.name,
                    title=r.get("change_title", ""),
                    summary=r.get("change_detail", r.get("status_summary", "")),
                    severity=r.get("severity", "info"),
                    created_at=now,
                )
                db.add(alert)

                if telegram_chat_id:
                    sent = send_alert(
                        chat_id=telegram_chat_id,
                        country_flag=country.flag,
                        country_name=country.name,
                        title=alert.title,
                        summary=alert.summary,
                        severity=alert.severity,
                    )
                    alert.sent_telegram = sent

        db.commit()
        logger.info("Проверка завершена.")
    except Exception as e:
        logger.error(f"Ошибка проверки: {e}", exc_info=True)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    s_db = next(get_db())
    interval_setting = s_db.query(Setting).filter_by(key="check_interval_hours").first()
    interval = int(interval_setting.value or 12) if interval_setting else 12
    s_db.close()
    start_scheduler(run_check, interval_hours=interval)
    yield
    stop_scheduler()


app = FastAPI(title="Nomad Tracker", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


# ── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    profile = db.query(Profile).first()
    countries = db.query(TrackedCountry).order_by(TrackedCountry.region, TrackedCountry.name).all()
    recent_alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(5).all()
    total_alerts = db.query(Alert).count()
    last_check = db.query(TrackedCountry).filter(TrackedCountry.last_check.isnot(None)).order_by(
        TrackedCountry.last_check.desc()
    ).first()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "profile": profile,
        "countries": countries,
        "recent_alerts": recent_alerts,
        "total_alerts": total_alerts,
        "last_check": last_check.last_check if last_check else None,
    })


@app.post("/check-now")
def check_now():
    import threading
    threading.Thread(target=run_check, daemon=True).start()
    return RedirectResponse("/?checking=1", status_code=303)


@app.post("/api/run-check")
def api_run_check(request: Request):
    secret = os.getenv("CHECK_SECRET", "")
    token = request.headers.get("X-Check-Token", "")
    if secret and token != secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    import threading
    threading.Thread(target=run_check, daemon=True).start()
    return {"status": "check started"}


# ── Alerts ───────────────────────────────────────────────────────────────────

@app.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request, db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()
    return templates.TemplateResponse("alerts.html", {"request": request, "alerts": alerts})


# ── Settings ─────────────────────────────────────────────────────────────────

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    profile = db.query(Profile).first()
    countries = db.query(TrackedCountry).order_by(TrackedCountry.region, TrackedCountry.name).all()
    settings = {s.key: s.value for s in db.query(Setting).all()}
    topics_active = set((profile.topics or "").split(",")) if profile else set()
    all_topics = [
        ("visa", "Визы и въезд"),
        ("residency", "ВНЖ и переезд"),
        ("nomad_visa", "Цифровая номадская виза"),
        ("tax", "Налоги"),
        ("banking", "Банки и счета"),
    ]
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "profile": profile,
        "countries": countries,
        "settings": settings,
        "topics_active": topics_active,
        "all_topics": all_topics,
        "default_countries": DEFAULT_COUNTRIES,
    })


@app.post("/settings/profile")
def save_profile(
    citizenship: str = Form(...),
    citizenship_label: str = Form(...),
    current_country: str = Form(""),
    topics: list[str] = Form(default=[]),
    goals: str = Form("nomad"),
    budget: str = Form(""),
    languages: str = Form(""),
    extra_citizenships: str = Form(""),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).first()
    if not profile:
        profile = Profile(id="default")
        db.add(profile)
    profile.citizenship = citizenship
    profile.citizenship_label = citizenship_label
    profile.current_country = current_country
    profile.topics = ",".join(topics) if topics else "visa"
    profile.goals = goals
    profile.budget = budget
    profile.languages = languages
    profile.extra_citizenships = extra_citizenships
    profile.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/settings?saved=profile", status_code=303)


@app.post("/settings/telegram")
def save_telegram(
    telegram_chat_id: str = Form(""),
    check_interval_hours: str = Form("12"),
    db: Session = Depends(get_db),
):
    for key, val in [("telegram_chat_id", telegram_chat_id), ("check_interval_hours", check_interval_hours)]:
        s = db.query(Setting).filter_by(key=key).first()
        if s:
            s.value = val
        else:
            db.add(Setting(key=key, value=val))
    db.commit()
    try:
        hours = int(check_interval_hours)
    except ValueError:
        hours = 12
    start_scheduler(run_check, interval_hours=hours)
    return RedirectResponse("/settings?saved=telegram", status_code=303)


@app.post("/settings/telegram/test")
def test_telegram(db: Session = Depends(get_db)):
    s = db.query(Setting).filter_by(key="telegram_chat_id").first()
    chat_id = s.value if s else ""
    ok = send_test_message(chat_id)
    return RedirectResponse(f"/settings?telegram_test={'ok' if ok else 'fail'}", status_code=303)


@app.post("/settings/countries/toggle/{code}")
def toggle_country(code: str, db: Session = Depends(get_db)):
    country = db.query(TrackedCountry).filter_by(code=code).first()
    if country:
        country.is_active = not country.is_active
        db.commit()
    return RedirectResponse("/settings#countries", status_code=303)


@app.post("/settings/countries/add")
def add_country(
    code: str = Form(...),
    name: str = Form(...),
    flag: str = Form("🏳️"),
    region: str = Form("Другое"),
    db: Session = Depends(get_db),
):
    code = code.upper().strip()
    if not db.query(TrackedCountry).filter_by(code=code).first():
        db.add(TrackedCountry(code=code, name=name, flag=flag, region=region))
        db.commit()
    return RedirectResponse("/settings#countries", status_code=303)


# ── Country Catalog ───────────────────────────────────────────────────────────

@app.get("/countries", response_class=HTMLResponse)
def countries_page(request: Request, q: str = "", db: Session = Depends(get_db)):
    tracked_codes = {c.code for c in db.query(TrackedCountry).all()}
    catalog = COUNTRY_CATALOG
    if q:
        q_lower = q.lower()
        catalog = [c for c in catalog if q_lower in c["name"].lower() or q_lower in c["code"].lower()]
    return templates.TemplateResponse("countries.html", {
        "request": request,
        "catalog": catalog,
        "tracked_codes": tracked_codes,
        "q": q,
    })


@app.post("/countries/add/{code}")
def add_from_catalog(code: str, db: Session = Depends(get_db)):
    item = next((c for c in COUNTRY_CATALOG if c["code"] == code), None)
    if item and not db.query(TrackedCountry).filter_by(code=code).first():
        db.add(TrackedCountry(code=item["code"], name=item["name"], flag=item["flag"], region=item["region"]))
        db.commit()
    return RedirectResponse("/countries", status_code=303)


@app.post("/settings/countries/delete/{code}")
def delete_country(code: str, db: Session = Depends(get_db)):
    country = db.query(TrackedCountry).filter_by(code=code).first()
    if country:
        db.delete(country)
        db.commit()
    return RedirectResponse("/settings#countries", status_code=303)


@app.post("/settings/countries/{code}/topics")
def save_country_topics(code: str, topics: list[str] = Form(default=[]), db: Session = Depends(get_db)):
    country = db.query(TrackedCountry).filter_by(code=code).first()
    if country:
        country.custom_topics = ",".join(topics)
        db.commit()
    return RedirectResponse("/settings#countries", status_code=303)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
