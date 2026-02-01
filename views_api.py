from http import HTTPStatus
import re
import zoneinfo

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from lnbits.core.crud import get_user
from lnbits.core.models import WalletTypeInfo
from lnbits.decorators import (
    check_admin,
    require_admin_key,
    require_invoice_key,
)
from lnbits.utils.exchange_rates import currencies

from .crud import (
    create_device,
    delete_device,
    get_device,
    get_devices,
    update_device,
)
from .helpers import encode_lnurl, is_valid_lnurl
from .models import CreateLnurldevice, Lnurldevice


def fix_device_lnurls(device: Lnurldevice, req: Request) -> Lnurldevice:
    """Ensure all switch LNURLs are properly bech32 encoded"""
    if not device.switches:
        return device

    base_url = str(req.url_for("devicetimer.lnurl_v2_params", device_id=device.id))
    for switch in device.switches:
        if not is_valid_lnurl(switch.lnurl):
            full_url = f"{base_url}?switch_id={switch.id}"
            switch.lnurl = encode_lnurl(full_url)

    return device

devicetimer_api_router = APIRouter()


@devicetimer_api_router.get("/api/v1/currencies", status_code=HTTPStatus.OK)
async def api_list_currencies_available() -> list[str]:
    return list(currencies.keys())


@devicetimer_api_router.get("/api/v1/timezones", status_code=HTTPStatus.OK)
async def api_list_timezones_available() -> list[str]:
    return sorted(zoneinfo.available_timezones(), key=str.lower)


@devicetimer_api_router.post(
    "/api/v1/device",
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(require_admin_key)],
)
async def api_lnurldevice_create(
    data: CreateLnurldevice, req: Request
) -> Lnurldevice:
    result = re.search(r"^\d{2}:\d{2}$", data.available_start)
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Opening time format must be hh:mm",
        )

    if data.timezone not in zoneinfo.available_timezones():
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Illegal timezone"
        )

    result = re.search(r"^\d{2}:\d{2}$", data.available_stop)
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Close time format must be hh:mm",
        )

    if data.maxperday is not None and str(data.maxperday).isnumeric():
        data.maxperday = int(data.maxperday)
    else:
        data.maxperday = 0

    return await create_device(data, req)


@devicetimer_api_router.put(
    "/api/v1/device/{lnurldevice_id}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(require_admin_key)],
)
async def api_lnurldevice_update(
    data: CreateLnurldevice, lnurldevice_id: str, req: Request
) -> Lnurldevice:
    result = re.search(r"^\d{2}:\d{2}$", data.available_start)
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Opening time format must be hh:mm",
        )

    if data.timezone not in zoneinfo.available_timezones():
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Illegal timezone"
        )

    result = re.search(r"^\d{2}:\d{2}$", data.available_stop)
    if not result:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Close time format must be hh:mm",
        )

    if data.maxperday is not None and str(data.maxperday).isnumeric():
        data.maxperday = int(data.maxperday)
    else:
        data.maxperday = 0

    return await update_device(lnurldevice_id, data, req)


@devicetimer_api_router.get("/api/v1/device", status_code=HTTPStatus.OK)
async def api_lnurldevices_retrieve(
    req: Request, wallet: WalletTypeInfo = Depends(require_invoice_key)
) -> list[Lnurldevice]:
    user = await get_user(wallet.wallet.user)
    assert user, "Lnurldevice cannot retrieve user"
    devices = await get_devices(user.wallet_ids)
    # Ensure all LNURLs are properly encoded
    return [fix_device_lnurls(d, req) for d in devices]


@devicetimer_api_router.get(
    "/api/v1/device/{lnurldevice_id}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(require_invoice_key)],
)
async def api_lnurldevice_retrieve(
    req: Request, lnurldevice_id: str
) -> Lnurldevice:
    device = await get_device(lnurldevice_id)
    if not device:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurldevice does not exist"
        )
    return fix_device_lnurls(device, req)


@devicetimer_api_router.delete(
    "/api/v1/device/{lnurldevice_id}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(require_admin_key)],
)
async def api_lnurldevice_delete(req: Request, lnurldevice_id: str):
    lnurldevice = await get_device(lnurldevice_id)
    if not lnurldevice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Lnurldevice does not exist."
        )
    await delete_device(lnurldevice_id)
    return {"deleted": True}
