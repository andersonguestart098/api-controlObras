from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings


_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled or _scheduler:
        return

    _scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    # Os jobs de snapshot serão adicionados depois que definirmos frequência e projetos.
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
