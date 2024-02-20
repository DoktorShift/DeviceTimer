import json
from typing import List, Optional

import shortuuid
from fastapi import Request
from lnurl import encode as lnurl_encode

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateLnurldevice, Lnurldevice, LnurldeviceSwitch, LnurldevicePayment, PaymentAllowed
from loguru import logger

from datetime import datetime
from time import time

import re

async def create_device(data: CreateLnurldevice, req: Request) -> Lnurldevice:
    logger.debug("create_device")
    device_id = urlsafe_short_hash()
    device_key = urlsafe_short_hash()

    if data.switches:
        url = req.url_for("devicetimer.lnurl_v2_params", device_id=device_id)
        for _switch in data.switches:
            _switch.id = shortuuid.uuid()[:8]
            _switch.lnurl = lnurl_encode(
                str(url)
                + "?switch_id="
                + str(_switch.id)
            )

    await db.execute(
        "INSERT INTO devicetimer.device (id, key, title, wallet, currency, available_start, available_stop, timeout, closed_url, wait_url, maxperday, switches) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            device_id,
            device_key,
            data.title,
            data.wallet,
            data.currency,
            data.available_start,
            data.available_stop,
            data.timeout,
            data.closed_url,
            data.wait_url,
            data.maxperday,
            json.dumps(data.switches, default=lambda x: x.dict()),
        ),
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
                    str(url)
                    + "?switch_id="
                    + str(_switch.id)
                )

    await db.execute(
        """
        UPDATE devicetimer.device SET
            title = ?,
            wallet = ?,
            currency = ?,
            available_start = ?,
            available_stop = ?,
            timeout = ?,
            closed_url = ?,
            maxperday = ?,    
            wait_url = ?,
            switches = ?
        WHERE id = ?
        """,
        (
            data.title,
            data.wallet,
            data.currency,
            data.available_start,
            data.available_stop,
            data.timeout,
            data.closed_url,
            data.maxperday,
            data.wait_url,
            json.dumps(data.switches, default=lambda x: x.dict()),
            device_id,
        ),
    )
    device = await get_device(device_id)
    assert device, "Lnurldevice was updated but could not be retrieved"
    return device


async def get_device(device_id: str) -> Optional[Lnurldevice]:
    row = await db.fetchone(
        "SELECT * FROM devicetimer.device WHERE id = ?", (device_id,)
    )
    if not row:
        return None

    device = Lnurldevice(**row)

    return device


async def get_devices(wallet_ids: List[str]) -> List[Lnurldevice]:

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM devicetimer.device WHERE wallet IN ({q})
        ORDER BY id
        """,
        (*wallet_ids,),
    )

    # this is needed for backwards compabtibility, before the LNURL were cached inside db
    devices = [Lnurldevice(**row) for row in rows]

    return devices


async def delete_device(lnurldevice_id: str) -> None:
    await db.execute(
        "DELETE FROM devicetimer.device WHERE id = ?", (lnurldevice_id,)
    )


async def create_payment(
    device_id: str,
    switch_id: str,
    payload: Optional[str] = None,
    payhash: Optional[str] = None,
    sats: Optional[int] = 0,
) -> LnurldevicePayment:


    payment_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO devicetimer.payment (
            id,
            deviceid,
            switchid,
            payload,
            payhash,
            sats
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (payment_id, device_id, switch_id, payload, payhash, sats),
    )
    payment = await get_payment(payment_id)
    assert payment, "Couldnt retrieve newly created payment"
    return payment


async def update_payment(
    payment_id: str, **kwargs
) -> LnurldevicePayment:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE devicetimer.payment SET {q} WHERE id = ?",
        (*kwargs.values(), payment_id),
    )
    dpayment = await get_payment(payment_id)
    assert dpayment, "Couldnt retrieve update LnurldevicePayment"
    return dpayment


async def get_payment(
    lnurldevicepayment_id: str,
) -> Optional[LnurldevicePayment]:
    row = await db.fetchone(
        "SELECT * FROM devicetimer.payment WHERE id = ?",
        (lnurldevicepayment_id,),
    )
    return LnurldevicePayment(**row) if row else None

async def get_payment_by_p(
    p: str,
) -> Optional[LnurldevicePayment]:
    row = await db.fetchone(
        "SELECT * FROM devicetimer.payment WHERE payhash = ?",
        (p,),
    )
    return LnurldevicePayment(**row) if row else None
    
async def get_lnurlpayload(
    lnurldevicepayment_payload: str,
) -> Optional[LnurldevicePayment]:
    row = await db.fetchone(
        "SELECT * FROM devicetimer.payment WHERE payload = ?",
        (lnurldevicepayment_payload,),
    )
    return LnurldevicePayment(**row) if row else None


async def get_last_payment(
    deviceid: str, switchid: str
) -> Optional[LnurldevicePayment]:
    row = await db.fetchone(
        "SELECT * FROM devicetimer.payment WHERE payhash = 'used' AND deviceid = ? AND switchid = ? ORDER BY timestamp DESC LIMIT 1",
        (deviceid, switchid),
    )
    return LnurldevicePayment(**row) if row else None

async def get_num_payments_after(
    deviceid: str, switchid: str, timestamp: int
) -> Optional[LnurldevicePayment]:
    row = await db.fetchone(
        "SELECT count(*) FROM devicetimer.payment WHERE payhash = 'used' AND deviceid = ? AND switchid = ? AND timestamp > ?",
        (deviceid, switchid, timestamp),
    )
    return row[0]

def get_minutes(timestr: str) -> int:
    """
    Convert a time string to minutes
    """
    result = re.search("^(\d{2})\:(\d{2})$",timestr)
    assert result, "illegal time format"        
    return int(result.groups()[0]) * 60 + int(result.groups()[1])

async def create_payment(
    device_id: str,
    switch_id: str,
    payload: Optional[str] = None,
    payhash: Optional[str] = None,
    sats: Optional[int] = 0,
) -> LnurldevicePayment:
    payment_id = urlsafe_short_hash()
    
    # Reduce the quantity + check the new quantity
    switch = await get_switch(switch_id)
    if switch.quantity is not None and switch.quantity > 0:
        new_quantity = switch.quantity - 1
        await update_switch_quantity(switch_id, new_quantity)
        if new_quantity == 0:
            # Logic to set the status to CLOSED (if necessary)
            pass
    else:
        # If sold out error message
        raise Exception("Product sold out")
    
    await db.execute(
        """
        INSERT INTO devicetimer.payment (
            id,
            deviceid,
            switchid,
            payload,
            payhash,
            sats
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (payment_id, device_id, switch_id, payload, payhash, sats),
    )
    
    payment = await get_payment(payment_id)
    assert payment, "Couldnt retrieve newly created payment"
    return payment

async def update_switch_quantity(switch_id: str, new_quantity: int):
    # Updating the quantity in the database
    await db.execute(
        "UPDATE devicetimer.switch SET quantity = ? WHERE id = ?",
        (new_quantity, switch_id),
    )

async def get_switch(switch_id: str):
    row = await db.fetchone(
        "SELECT * FROM devicetimer.switch WHERE id = ?",
        (switch_id,),
    )
    if row:
        return LnurldeviceSwitch(**row)
    else:
        return None

async def get_payment_allowed(
        device: Lnurldevice, switch: LnurldeviceSwitch
    ) -> PaymentAllowed:

async def get_payment_allowed(
        device: Lnurldevice, switch: LnurldeviceSwitch
    ) -> PaymentAllowed:

    if switch.quantity is not None and switch.quantity <= 0:
        return PaymentAllowed.CLOSED

    now = datetime.now()
    minutes = now.hour * 60 + now.minute
    
    start_minutes = get_minutes(device.available_start)
    stop_minutes = get_minutes(device.available_stop)
    if stop_minutes <= start_minutes:
        if (minutes < start_minutes or minutes > stop_minutes + (60*24)) and (minutes < start_minutes - (60*24) or minutes > stop_minutes):
            return PaymentAllowed.CLOSED
    else:
        if ( minutes < start_minutes or minutes > stop_minutes):
            return PaymentAllowed.CLOSED
    
    now = time()        
    if device.maxperday is not None and device.maxperday > 0:
        num_payments = await get_num_payments_after(deviceid=device.id,switchid=switch.id,timestamp=now - 86400)    
        if num_payments >= device.maxperday:
            return PaymentAllowed.CLOSED

    last_payment = await get_last_payment(deviceid=device.id,switchid=switch.id)
    if not last_payment:
        return PaymentAllowed.OPEN
    
    logger.info(f"Last payment at {last_payment.timestamp} {now - int(last_payment.timestamp)}")    
    if last_payment is not None and now - int(last_payment.timestamp) < device.timeout:
        return PaymentAllowed.WAIT

    return PaymentAllowed.OPEN
