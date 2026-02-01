from http import HTTPStatus
import json

from fastapi import APIRouter, HTTPException, Query, Request

from lnbits.core.services import create_invoice
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis

from .models import PaymentAllowed
from .crud import (
    create_payment,
    get_device,
    get_payment,
    update_payment,
    get_payment_allowed,
)

devicetimer_lnurl_router = APIRouter()


@devicetimer_lnurl_router.get(
    "/api/v1/lnurl/{device_id}",
    status_code=HTTPStatus.OK,
    name="devicetimer.lnurl_v1_params",
)
async def lnurl_v1_params(request: Request, device_id: str, switch_id: str):
    return await lnurl_params(request, device_id, switch_id)


def create_payment_memo(device, switch) -> str:
    text = ""
    if device.title:
        text += device.title
        text += " "
    if switch.label:
        text += switch.label
    return text.strip()


@devicetimer_lnurl_router.get(
    "/api/v2/lnurl/{device_id}",
    status_code=HTTPStatus.OK,
    name="devicetimer.lnurl_v2_params",
)
async def lnurl_v2_params(request: Request, device_id: str, switch_id: str):
    return await lnurl_params(request, device_id, switch_id)


async def lnurl_params(request: Request, device_id: str, switch_id: str):
    # find the device
    device = await get_device(device_id)
    if not device:
        return {
            "status": "ERROR",
            "reason": f"lnurldevice {device_id} not found on this server",
        }

    # find the switch
    switch = None
    if device.switches:
        for _switch in device.switches:
            if _switch.id == switch_id:
                switch = _switch
                break
    if not switch:
        return {"status": "ERROR", "reason": "Switch params wrong"}

    result = await get_payment_allowed(device, switch)
    if result == PaymentAllowed.CLOSED:
        return {"status": "ERROR", "reason": "Payment not allowed outside opening hours"}
    if result == PaymentAllowed.WAIT:
        return {"status": "ERROR", "reason": "Payment not allowed due to recent payment"}

    price_msat = int(
        (
            await fiat_amount_as_satoshis(float(switch.amount), device.currency)
            if device.currency != "sat"
            else float(switch.amount)
        )
        * 1000
    )

    lnurldevicepayment = await create_payment(
        device_id=device.id,
        switch_id=switch.id,
        payload=f"{switch.gpio_pin}-{switch.gpio_duration}",
        sats=price_msat,
        payhash="pending",
    )
    if not lnurldevicepayment:
        return {"status": "ERROR", "reason": "Could not create payment."}

    return {
        "tag": "payRequest",
        "callback": str(
            request.url_for("devicetimer.lnurl_callback", paymentid=lnurldevicepayment.id)
        ),
        "minSendable": price_msat,
        "maxSendable": price_msat,
        "metadata": json.dumps([["text/plain", create_payment_memo(device, switch)]]),
    }


@devicetimer_lnurl_router.get(
    "/api/v1/lnurl/cb/{paymentid}",
    status_code=HTTPStatus.OK,
    name="devicetimer.lnurl_callback",
)
async def lnurl_callback(
    request: Request,
    paymentid: str,
    amount: int = Query(..., description="Amount in millisatoshis"),
):
    payment = await get_payment(paymentid)
    if not payment:
        return {"status": "ERROR", "reason": "Payment not found."}

    if payment.payhash == "used":
        return {"status": "ERROR", "reason": "Payment already used."}

    device = await get_device(payment.deviceid)
    if not device:
        return {"status": "ERROR", "reason": "Device not found."}

    switch = None
    for _switch in device.switches:
        if _switch.id == payment.switchid:
            switch = _switch
            break

    if not switch:
        return {"status": "ERROR", "reason": "Switch not found."}

    # Validate amount matches expected
    if amount != payment.sats:
        return {"status": "ERROR", "reason": f"Amount mismatch. Expected {payment.sats} msats."}

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=device.wallet,
            amount=int(amount / 1000),
            memo=create_payment_memo(device, switch),
            unhashed_description=json.dumps(
                [["text/plain", create_payment_memo(device, switch)]]
            ).encode(),
            extra={
                "tag": "DeviceTimer",
                "Device": device.id,
                "Switch": switch.id,
                "amount": switch.amount,
                "currency": device.currency,
                "id": paymentid,
                "received": False,
                "fulfilled": False,
            },
        )

        await update_payment(payment_id=paymentid, payhash=payment_hash)

        return {
            "pr": payment_request,
            "routes": [],
        }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}
