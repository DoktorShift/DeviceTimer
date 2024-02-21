from http import HTTPStatus

from fastapi import Depends, HTTPException, Query, Request
from loguru import logger
import re

from lnbits.core.crud import get_user, update_payment_extra
from lnbits.decorators import (
    WalletTypeInfo,
    check_admin,
    get_key_type,
    require_admin_key,
)
from lnbits.utils.exchange_rates import currencies

from . import devicetimer_ext, scheduled_tasks
from .crud import (
    create_device,
    delete_device,
    get_device,
    get_devices,
    update_device,
    get_payment
)
from .models import CreateLnurldevice



@devicetimer_ext.get("/api/v1/currencies")
async def api_list_currencies_available():
    return list(currencies.keys())


@devicetimer_ext.post("/api/v1/device", dependencies=[Depends(require_admin_key)])
async def api_lnurldevice_create(data: CreateLnurldevice, req: Request):
    result = re.search("^\d{2}\:\d{2}$",data.available_start)
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Opening time format must be hh:mm"
        )
    
    result = re.search("^\d{2}\:\d{2}$",data.available_stop)
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Close time format must be hh:mm"
        )

    if str(data.maxperday).isnumeric() and int(data.maxperday) >= 0:
        data.maxperday = int(data.maxperday)
    else:
        data.maxperday = 0      

    return await create_device(data, req)


@devicetimer_ext.put(
    "/api/v1/device/{lnurldevice_id}", dependencies=[Depends(require_admin_key)]
)
async def api_lnurldevice_update(
    data: CreateLnurldevice, lnurldevice_id: str, req: Request
):
    result = re.search("^\d{2}\:\d{2}$",data.available_start)
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Opening time format must be hh:mm"
        )
    
    result = re.search("^\d{2}\:\d{2}$",data.available_stop)
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Close time format must be hh:mm"
        )

    if str(data.maxperday).isnumeric() and int(data.maxperday) >= 0:
        data.maxperday = int(data.maxperday)
    else:
        data.maxperday = 0      

    return await update_device(lnurldevice_id, data, req)

@devicetimer_ext.get("/api/v1/device")
async def api_lnurldevices_retrieve(
    req: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    user = await get_user(wallet.wallet.user)
    assert user, "Lnurldevice cannot retrieve user"
    devices =  await get_devices(user.wallet_ids)

    return devices


@devicetimer_ext.get(
    "/api/v1/device/{lnurldevice_id}", dependencies=[Depends(get_key_type)]
)
async def api_lnurldevice_retrieve(req: Request, lnurldevice_id: str):
    device = await get_device(lnurldevice_id)
    if not device:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurldevice does not exist"
        )
    
    return device

@devicetimer_ext.delete(
    "/api/v1/device/{lnurldevice_id}", dependencies=[Depends(require_admin_key)]
)
async def api_lnurldevice_delete(req: Request, lnurldevice_id: str):
    lnurldevice = await get_device(lnurldevice_id)
    if not lnurldevice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Lnurldevice does not exist."
        )

    await delete_device(lnurldevice_id)


@devicetimer_ext.delete(
    "/api/v1", status_code=HTTPStatus.OK, dependencies=[Depends(check_admin)]
)
async def api_stop():
    for t in scheduled_tasks:
        try:
            t.cancel()
        except Exception as ex:
            logger.warning(ex)

    return {"success": True}
