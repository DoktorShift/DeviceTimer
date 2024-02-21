import asyncio

from lnbits.core.models import Payment
from lnbits.core.services import websocketUpdater
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_payment, update_payment, get_device

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

    return await websocketUpdater(
        device_payment.deviceid,
        f"{switch.gpio_pin}-{switch.gpio_duration}"
    )
