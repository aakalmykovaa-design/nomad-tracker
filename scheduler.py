import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler = BackgroundScheduler(timezone="Europe/Moscow")


def start_scheduler(run_check_fn, interval_hours: int = 12):
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler.add_job(run_check_fn, "interval", hours=interval_hours, id="daily_check", replace_existing=True)
    _scheduler.start()
    logger.info(f"Планировщик запущен: проверка каждые {interval_hours} ч.")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
