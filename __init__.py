import asyncio

from fastapi import APIRouter
from loguru import logger

from .crud import db
from .tasks import wait_for_paid_invoices
from .views import devicetimer_generic_router
from .views_api import devicetimer_api_router
from .lnurl import devicetimer_lnurl_router
from .websocket import devicetimer_websocket_router

scheduled_tasks: list[asyncio.Task] = []

devicetimer_static_files = [
    {
        "path": "/devicetimer/static",
        "name": "devicetimer_static",
    }
]

devicetimer_ext: APIRouter = APIRouter(prefix="/devicetimer", tags=["devicetimer"])
devicetimer_ext.include_router(devicetimer_generic_router)
devicetimer_ext.include_router(devicetimer_api_router)
devicetimer_ext.include_router(devicetimer_lnurl_router)
devicetimer_ext.include_router(devicetimer_websocket_router)


def devicetimer_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def devicetimer_start():
    from lnbits.tasks import create_permanent_unique_task

    task = create_permanent_unique_task("ext_devicetimer", wait_for_paid_invoices)
    scheduled_tasks.append(task)


__all__ = [
    "db",
    "devicetimer_ext",
    "devicetimer_start",
    "devicetimer_stop",
    "devicetimer_static_files",
]
