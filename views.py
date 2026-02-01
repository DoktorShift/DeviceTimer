from http import HTTPStatus
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, Response

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer
from lnbits.settings import settings

from loguru import logger
import pyqrcode
import httpx

from .crud import get_device, get_payment_allowed
from .helpers import encode_lnurl, is_valid_lnurl
from .models import PaymentAllowed

devicetimer_generic_router = APIRouter()


def devicetimer_renderer():
    return template_renderer(["devicetimer/templates"])


@devicetimer_generic_router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return devicetimer_renderer().TemplateResponse(
        "devicetimer/index.html", {"request": request, "user": user.json()}
    )


def proxy_allowed(url: str | None) -> bool:
    """Check if URL is allowed to be proxied"""
    if not url:
        return False
    if "localhost" in url.lower():
        return False
    if "127.0.0.1" in url:
        return False
    if url.startswith("https://"):
        return True
    return False


def default_unavailable_image() -> FileResponse:
    image_path = Path(
        settings.lnbits_extensions_path,
        "extensions",
        "devicetimer",
        "static",
        "image",
        "unavailable.png",
    )
    return FileResponse(
        image_path,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@devicetimer_generic_router.get("/device/{deviceid}/{switchid}/qrcode")
async def devicetimer_qrcode(request: Request, deviceid: str, switchid: str):
    """
    Return the landing page for a device where the customer
    can initiate the feeding or when it is allowed, an LNURL payment
    """
    device = await get_device(deviceid)
    if not device:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Device does not exist"
        )

    switch = None
    for _switch in device.switches:
        if _switch.id == switchid:
            switch = _switch
            break

    if not switch:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Switch does not exist"
        )

    result = await get_payment_allowed(device, switch)
    logger.info(f"get_payment_allowed result = {result}")

    if result == PaymentAllowed.CLOSED:
        if proxy_allowed(device.closed_url):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(device.closed_url)
                    return Response(response.content)
            except Exception as e:
                logger.error(f"Failed to retrieve closed image: {e}")
        return default_unavailable_image()

    if result == PaymentAllowed.WAIT:
        if proxy_allowed(device.wait_url):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(device.wait_url)
                    return Response(response.content)
            except Exception as e:
                logger.error(f"Failed to retrieve wait image: {e}")
        return default_unavailable_image()

    # Ensure LNURL is properly bech32 encoded
    lnurl_value = switch.lnurl
    if not is_valid_lnurl(lnurl_value):
        base_url = str(request.url_for("devicetimer.lnurl_v2_params", device_id=deviceid))
        full_url = f"{base_url}?switch_id={switchid}"
        lnurl_value = encode_lnurl(full_url)
        logger.info(f"Generated LNURL on-the-fly for QR: {lnurl_value[:20]}...")

    qr = pyqrcode.create(lnurl_value)
    stream = BytesIO()
    qr.svg(stream, scale=3)
    stream.seek(0)

    async def _generator(stream: BytesIO):
        yield stream.getvalue()

    return StreamingResponse(
        _generator(stream),
        headers={
            "Content-Type": "image/svg+xml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
