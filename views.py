from http import HTTPStatus

from fastapi import Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, Response

from lnbits.core.crud import update_payment_status
from lnbits.core.models import User
from lnbits.core.views.api import api_payment
from lnbits.decorators import check_user_exists

from . import devicetimer_ext, devicetimer_renderer, devicetimer_static_files
from .crud import get_device, get_payment, get_payment_allowed

from .models import PaymentAllowed

from loguru import logger
import pyqrcode
from io import BytesIO

import os
import httpx

templates = Jinja2Templates(directory="templates")


@devicetimer_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return devicetimer_renderer().TemplateResponse(
        "devicetimer/index.html",
        {"request": request, "user": user.dict()},
    )

def proxy_allowed(url: str):
    if not url:
        raise
    if 'localhost' in url.lower():
        raise
    if '127.0.0.1' in url:
        raise
    if url.startswith("https://"):
        return
    raise

def default_unavailable_image() -> FileResponse:
    return FileResponse(
        "lnbits/extensions/devicetimer/static/image/unavailable.png",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        })

@devicetimer_ext.get("/device/{deviceid}/{switchid}/qrcode")
async def devicetimer_qrcode(request: Request, deviceid: str, switchid: str):
    """
    return the landing page for a device where the customer
    kan initiate the feeding or when it is a allowed, an LNURL payment
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

    if not switch:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Switch does not exist"
        )

    result = await get_payment_allowed(device,switch)
    logger.info(f"get_payment_allowed result = {result}")
    
    if result == PaymentAllowed.CLOSED:
        try:
            proxy_allowed(device.closed_url)
            async with httpx.AsyncClient() as client:                              
                response = await client.get(device.closed_url)                
                return Response(response.content)
        except:
            logger.error("Failed to retrieve image")
            return default_unavailable_image()
    
    if result == PaymentAllowed.WAIT:
        try:  
            proxy_allowed(device.wait_url)
            async with httpx.AsyncClient() as client: 
                response = await client.get(device.wait_url)
                return Response(response.content)
        except:
            logger.error("Failed to retrieve image")
            return default_unavailable_image()
                
    qr = pyqrcode.create(switch.lnurl)
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
    
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND, detail="Unknown Feeder state"
    )
    

