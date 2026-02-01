"""Helper utilities for DeviceTimer extension"""

from lnurl import Lnurl
from loguru import logger


def encode_lnurl(url: str) -> str:
    """
    Encode a URL to LNURL bech32 format.

    Args:
        url: The URL to encode (must be https for production)

    Returns:
        Bech32 encoded LNURL string (uppercase, starting with LNURL1...)
    """
    try:
        lnurl_obj = Lnurl(url)
        encoded = lnurl_obj.bech32
        return encoded.upper()
    except Exception as e:
        logger.error(f"Failed to encode LNURL: {e}, url: {url}")
        raise ValueError(f"Invalid URL for LNURL encoding: {url}") from e


def is_valid_lnurl(value: str) -> bool:
    """
    Check if a string is a valid bech32 encoded LNURL.

    Args:
        value: The string to check

    Returns:
        True if valid LNURL format, False otherwise
    """
    if not value:
        return False
    return value.upper().startswith("LNURL1")
