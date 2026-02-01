import json
from typing import Optional

import shortuuid
from fastapi import Request
from lnurl import encode as lnurl_encode
from loguru import logger

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .models import (
    CreateLnurldevice,
    Lnurldevice,
    LnurldeviceSwitch,
    LnurldevicePayment,
    PaymentAllowed,
)

from datetime import datetime
from zoneinfo import ZoneInfo
from time import time
import re

db = Database("ext_devicetimer")


async def create_device(data: CreateLnurldevice, req: Request) -> Lnurldevice:
    logger.debug("create_device")
    device_id = urlsafe_short_hash()
    device_key = urlsafe_short_hash()

    if data.switches:
        url = req.url_for("devicetimer.lnurl_v2_params", device_id=device_id)
        for _switch in data.switches:
            _switch.id = shortuuid.uuid()[:8]
            _switch.lnurl = lnurl_encode(
                str(url) + "?switch_id=" + str(_switch.id)
            )

    switches_json = json.dumps(
        [s.dict() for s in data.switches] if data.switches else []
    )

    await db.execute(
        """
        INSERT INTO devicetimer.device
        (id, key, title, wallet, currency, available_start, available_stop,
         timeout, timezone, closed_url, wait_url, maxperday, switches)
        VALUES (:id, :key, :title, :wallet, :currency, :available_start,
                :available_stop, :timeout, :timezone, :closed_url, :wait_url,
                :maxperday, :switches)
        """,
        {
            "id": device_id,
            "key": device_key,
            "title": data.title,
            "wallet": data.wallet,
            "currency": data.currency,
            "available_start": data.available_start,
            "available_stop": data.available_stop,
            "timeout": data.timeout,
            "timezone": data.timezone,
            "closed_url": data.closed_url,
            "wait_url": data.wait_url,
            "maxperday": data.maxperday or 0,
            "switches": switches_json,
        },
    )

    device = await get_device(device_id)
    assert device, "Lnurldevice was created but could not be retrieved"
    return device


async def update_device(
    device_id: str, data: CreateLnurldevice, req: Request
) -> Lnurldevice:
    if data.switches:
        url = req.url_for("devicetimer.lnurl_v2_params", device_id=device_id)
        for _switch in data.switches:
            if _switch.id is None:
                _switch.id = shortuuid.uuid()[:8]
                _switch.lnurl = lnurl_encode(
                    str(url) + "?switch_id=" + str(_switch.id)
                )

    switches_json = json.dumps(
        [s.dict() for s in data.switches] if data.switches else []
    )

    await db.execute(
        """
        UPDATE devicetimer.device SET
            title = :title,
            wallet = :wallet,
            currency = :currency,
            available_start = :available_start,
            available_stop = :available_stop,
            timeout = :timeout,
            timezone = :timezone,
            closed_url = :closed_url,
            maxperday = :maxperday,
            wait_url = :wait_url,
            switches = :switches
        WHERE id = :id
        """,
        {
            "title": data.title,
            "wallet": data.wallet,
            "currency": data.currency,
            "available_start": data.available_start,
            "available_stop": data.available_stop,
            "timeout": data.timeout,
            "timezone": data.timezone,
            "closed_url": data.closed_url,
            "maxperday": data.maxperday or 0,
            "wait_url": data.wait_url,
            "switches": switches_json,
            "id": device_id,
        },
    )
    device = await get_device(device_id)
    assert device, "Lnurldevice was updated but could not be retrieved"
    return device


def _parse_device(row) -> Lnurldevice:
    """Parse a database row into a Lnurldevice model"""
    data = dict(row)
    # Parse switches from JSON string
    if data.get("switches") and isinstance(data["switches"], str):
        try:
            switches_data = json.loads(data["switches"])
            data["switches"] = [LnurldeviceSwitch(**s) for s in switches_data]
        except (json.JSONDecodeError, TypeError):
            data["switches"] = []
    elif not data.get("switches"):
        data["switches"] = []
    return Lnurldevice(**data)


async def get_device(device_id: str) -> Optional[Lnurldevice]:
    row = await db.fetchone(
        "SELECT * FROM devicetimer.device WHERE id = :id",
        {"id": device_id},
    )
    if not row:
        return None
    return _parse_device(row)


async def get_devices(wallet_ids: list[str]) -> list[Lnurldevice]:
    if not wallet_ids:
        return []
    q = ",".join([f"'{w}'" for w in wallet_ids])
    rows = await db.fetchall(
        f"SELECT * FROM devicetimer.device WHERE wallet IN ({q}) ORDER BY id",
    )
    return [_parse_device(row) for row in rows]


async def delete_device(lnurldevice_id: str) -> None:
    await db.execute(
        "DELETE FROM devicetimer.device WHERE id = :id",
        {"id": lnurldevice_id},
    )


async def create_payment(
    device_id: str,
    switch_id: str,
    payload: str | None = None,
    payhash: str | None = None,
    sats: int = 0,
) -> LnurldevicePayment:
    payment_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO devicetimer.payment
        (id, deviceid, switchid, payload, payhash, sats)
        VALUES (:id, :deviceid, :switchid, :payload, :payhash, :sats)
        """,
        {
            "id": payment_id,
            "deviceid": device_id,
            "switchid": switch_id,
            "payload": payload or "",
            "payhash": payhash or "",
            "sats": sats,
        },
    )
    payment = await get_payment(payment_id)
    assert payment, "Could not retrieve newly created payment"
    return payment


async def update_payment(payment_id: str, **kwargs) -> LnurldevicePayment:
    set_clause = ", ".join([f"{field} = :{field}" for field in kwargs.keys()])
    params = {**kwargs, "id": payment_id}
    await db.execute(
        f"UPDATE devicetimer.payment SET {set_clause} WHERE id = :id",
        params,
    )
    dpayment = await get_payment(payment_id)
    assert dpayment, "Could not retrieve updated LnurldevicePayment"
    return dpayment


async def get_payment(lnurldevicepayment_id: str) -> Optional[LnurldevicePayment]:
    return await db.fetchone(
        "SELECT * FROM devicetimer.payment WHERE id = :id",
        {"id": lnurldevicepayment_id},
        LnurldevicePayment,
    )


async def get_payment_by_p(p: str) -> Optional[LnurldevicePayment]:
    return await db.fetchone(
        "SELECT * FROM devicetimer.payment WHERE payhash = :payhash",
        {"payhash": p},
        LnurldevicePayment,
    )


async def get_lnurlpayload(
    lnurldevicepayment_payload: str,
) -> Optional[LnurldevicePayment]:
    return await db.fetchone(
        "SELECT * FROM devicetimer.payment WHERE payload = :payload",
        {"payload": lnurldevicepayment_payload},
        LnurldevicePayment,
    )


async def get_last_payment(
    deviceid: str, switchid: str
) -> Optional[LnurldevicePayment]:
    return await db.fetchone(
        """SELECT * FROM devicetimer.payment
           WHERE payhash = 'used' AND deviceid = :deviceid AND switchid = :switchid
           ORDER BY timestamp DESC LIMIT 1""",
        {"deviceid": deviceid, "switchid": switchid},
        LnurldevicePayment,
    )


async def get_num_payments_after(
    deviceid: str, switchid: str, timestamp: float
) -> int:
    row = await db.fetchone(
        """SELECT count(*) as count FROM devicetimer.payment
           WHERE payhash = 'used' AND deviceid = :deviceid
           AND switchid = :switchid AND timestamp > :timestamp""",
        {"deviceid": deviceid, "switchid": switchid, "timestamp": str(int(timestamp))},
    )
    if row:
        return int(row.count) if hasattr(row, 'count') else int(row[0])
    return 0


def get_minutes(timestr: str) -> int:
    """Convert a time string to minutes"""
    result = re.search(r"^(\d{2}):(\d{2})$", timestr)
    assert result, "illegal time format"
    return int(result.groups()[0]) * 60 + int(result.groups()[1])


async def get_payment_allowed(
    device: Lnurldevice, switch: LnurldeviceSwitch
) -> PaymentAllowed:
    now = datetime.now(ZoneInfo(device.timezone))
    minutes = now.hour * 60 + now.minute

    start_minutes = get_minutes(device.available_start)
    stop_minutes = get_minutes(device.available_stop)

    if stop_minutes <= start_minutes:
        if (minutes < start_minutes or minutes > stop_minutes + (60 * 24)) and (
            minutes < start_minutes - (60 * 24) or minutes > stop_minutes
        ):
            return PaymentAllowed.CLOSED
    else:
        if minutes < start_minutes or minutes > stop_minutes:
            return PaymentAllowed.CLOSED

    now_ts = time()
    if device.maxperday is not None and device.maxperday > 0:
        num_payments = await get_num_payments_after(
            deviceid=device.id, switchid=switch.id, timestamp=now_ts - 86400
        )
        if num_payments >= device.maxperday:
            return PaymentAllowed.CLOSED

    last_payment = await get_last_payment(deviceid=device.id, switchid=switch.id)
    if not last_payment:
        return PaymentAllowed.OPEN

    logger.info(
        f"Last payment at {last_payment.timestamp} {now_ts - int(last_payment.timestamp)}"
    )
    if last_payment is not None and now_ts - int(last_payment.timestamp) < device.timeout:
        return PaymentAllowed.WAIT

    return PaymentAllowed.OPEN
