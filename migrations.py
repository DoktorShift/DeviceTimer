import json

from lnbits.db import Database

async def m001_initial(db):
    """
    Initial device table.
    """
    await db.execute(
        f"""
        CREATE TABLE devicetimer.device (
            id TEXT NOT NULL PRIMARY KEY,
            key TEXT NOT NULL,
            title TEXT NOT NULL,
            wallet TEXT NOT NULL,
            currency TEXT NOT NULL,
            switches TEXT,
            available_start TEXT DEFAULT '09:00',
            available_stop TEXT DEFAULT '17:00',
            timeout INT DEFAULT 30,
            timestamp TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )

    
    await db.execute(
        f"""
        CREATE TABLE devicetimer.payment (
            id TEXT NOT NULL PRIMARY KEY,
            deviceid TEXT NOT NULL,
            switchid TEXT NOT NULL,
            payhash TEXT,
            payload TEXT NOT NULL,
            sats {db.big_int},
            timestamp TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )

async def m002_redux(db):
    await db.execute(
        f"""
        ALTER TABLE devicetimer.device ADD COLUMN closed_url TEXT
        """
    )

async def m003_redux(db):
    await db.execute(
        f"""
        ALTER TABLE devicetimer.device ADD COLUMN wait_url TEXT
        """
    )

async def m004_redux(db):
    await db.execute(
        f"""
        ALTER TABLE devicetimer.device ADD COLUMN maxperday INT DEFAULT 0
        """
    )
