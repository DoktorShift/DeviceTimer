import asyncio
from typing import List

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_devicetimer")

devicetimer_ext: APIRouter = APIRouter(prefix="/devicetimer", tags=["devicetimer"])

scheduled_tasks: List[asyncio.Task] = []

devicetimer_static_files = [
    {
        "path": "/devicetimer/static",
        "app": StaticFiles(directory="lnbits/extensions/devicetimer/static"),
        "name": "devicetimer_static",
    }
]


def devicetimer_renderer():
    return template_renderer(["lnbits/extensions/devicetimer/templates"])


from .lnurl import *  # noqa: F401,F403
from .tasks import wait_for_paid_invoices
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403


def devicetimer_start():
    loop = asyncio.get_event_loop()
    task = loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
    scheduled_tasks.append(task)
