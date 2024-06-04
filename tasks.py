import asyncio

from lnbits.core.models import Payment

from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_payment, update_payment, get_device

from lnbits.extension_manager import version_parse
from lnbits.settings import settings

# from LNbits release 0.12.6 the websocketUpdater function was renamed to websocket_updater
print(settings.version)
print(version_parse(settings.version))
if version_parse(settings.version) >= version_parse("0.12.6"):
    from lnbits.core.services import websocket_updater
else:
    from lnbits.core.services import websocketUpdater as websocket_updater

async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    
    # do not process paid invoices that are not for this extension
    if payment.extra.get("tag") != "DeviceTimer":
        return

    device_payment = await get_payment(payment.extra["id"])

    if not device_payment:
        return
    if device_payment.payhash == "used":
        return

    device_payment = await update_payment(
        payment_id=payment.extra["id"], payhash="used"
    )

    device = await get_device(device_payment.deviceid)
    if not device:
        return

    switch = None
    for _switch in device.switches:
        if _switch.id == device_payment.switchid:
            switch = _switch
            break
    if not switch:
        return

    return await websocket_updater(
        device_payment.deviceid,
        f"{switch.gpio_pin}-{switch.gpio_duration}"
    )
