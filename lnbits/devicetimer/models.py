import json
from sqlite3 import Row
from typing import List, Optional
from enum import Enum

from lnurl.types import LnurlPayMetadata
from pydantic import BaseModel, Json, Field

class PaymentAllowed(Enum):
    OPEN = 1
    CLOSED = 2
    WAIT = 3

class LnurldeviceSwitch(BaseModel):
    id: Optional[str]
    amount: float = 0.0
    gpio_pin: int = 21
    gpio_duration: int = 2100
    lnurl: Optional[str]
    label: Optional[str]
    quantity: Optional[int]

class CreateLnurldevice(BaseModel):
    title: str
    wallet: str
    currency: str
    available_start: str
    available_stop: str
    timeout: int
    maxperday: Optional[int]
    closed_url: Optional[str]
    wait_url: Optional[str]
    switches: Optional[List[LnurldeviceSwitch]]
    quantity: Optional[int] = Field(default=0, ge=0)
    


class Lnurldevice(BaseModel):
    id: str
    key: str
    title: str
    wallet: str
    currency: str
    switches: Optional[Json[List[LnurldeviceSwitch]]]
    timestamp: str
    available_start: str
    available_stop: str
    timeout: int
    maxperday: Optional[int]
    closed_url: Optional[str]
    wait_url: Optional[str]

    @classmethod
    def from_row(cls, row: Row) -> "Lnurldevice":
        return cls(**dict(row))

class LnurldevicePayment(BaseModel):
    id: str
    deviceid: str
    payhash: str
    payload: str
    switchid: str
    sats: int
    timestamp: str

    @classmethod
    def from_row(cls, row: Row) -> "LnurldevicePayment":
        return cls(**dict(row))
