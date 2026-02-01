from typing import List, Optional
from enum import Enum

from pydantic import BaseModel


class PaymentAllowed(Enum):
    OPEN = 1
    CLOSED = 2
    WAIT = 3


class LnurldeviceSwitch(BaseModel):
    id: Optional[str] = None
    amount: float = 0.0
    gpio_pin: int = 21
    gpio_duration: int = 2100
    lnurl: Optional[str] = None
    label: Optional[str] = None


class CreateLnurldevice(BaseModel):
    title: str
    wallet: str
    currency: str
    available_start: str
    available_stop: str
    timeout: int
    timezone: str
    maxperday: Optional[int] = None
    closed_url: Optional[str] = None
    wait_url: Optional[str] = None
    switches: Optional[List[LnurldeviceSwitch]] = None


class Lnurldevice(BaseModel):
    id: str
    key: str
    title: str
    wallet: str
    currency: str
    switches: List[LnurldeviceSwitch] = []
    timestamp: str = ""
    available_start: str
    available_stop: str
    timeout: int
    timezone: str
    maxperday: Optional[int] = None
    closed_url: Optional[str] = None
    wait_url: Optional[str] = None

class LnurldevicePayment(BaseModel):
    id: str
    deviceid: str
    payhash: str
    payload: str
    switchid: str
    sats: int
    timestamp: str = ""
