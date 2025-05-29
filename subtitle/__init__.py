import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from static import config

from .utils import add_subtitles_all

async def init():
    '初始化'
    interval = config.subtitle['check_interval']
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_refresh, trigger="interval", seconds=interval)
    scheduler.start()
    logger.debug(f"Subtitle checking scheduler started (Interval: {interval}s)")
    return scheduler

async def scheduled_refresh():
    '定时操作'
    logger.debug("Start checking subtitles...")
    await add_subtitles_all()
