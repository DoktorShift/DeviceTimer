"""
WebSocket management for DeviceTimer extension.

Handles device connections and message broadcasting.
Tracks connected hardware devices to show real-time status in UI.
Browser connections (for watching payments) are tracked separately.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger
from typing import Dict, Set, Optional

devicetimer_websocket_router = APIRouter()

# Track hardware device connections: device_id -> set of WebSocket connections
_hardware_clients: Dict[str, Set[WebSocket]] = {}

# Track browser connections (for payment notifications in UI)
_browser_clients: Dict[str, Set[WebSocket]] = {}


def get_connected_device_ids() -> list[str]:
    """Return list of device IDs with active hardware connections."""
    return list(_hardware_clients.keys())


def is_device_connected(device_id: str) -> bool:
    """Check if a hardware device has any active WebSocket connections."""
    return device_id in _hardware_clients and len(_hardware_clients[device_id]) > 0


async def send_to_device(device_id: str, message: str) -> bool:
    """
    Send a message to all WebSocket connections for a device (hardware + browser).
    Returns True if message was sent to at least one client.
    """
    sent = False

    # Send to hardware clients
    if device_id in _hardware_clients:
        dead_connections: Set[WebSocket] = set()
        for websocket in _hardware_clients[device_id]:
            try:
                await websocket.send_text(message)
                sent = True
            except Exception as e:
                logger.debug(f"Failed to send to hardware: {e}")
                dead_connections.add(websocket)
        for ws in dead_connections:
            _hardware_clients[device_id].discard(ws)
        if not _hardware_clients[device_id]:
            del _hardware_clients[device_id]

    # Send to browser clients (so UI shows payment received)
    if device_id in _browser_clients:
        dead_connections = set()
        for websocket in _browser_clients[device_id]:
            try:
                await websocket.send_text(message)
                sent = True
            except Exception as e:
                logger.debug(f"Failed to send to browser: {e}")
                dead_connections.add(websocket)
        for ws in dead_connections:
            _browser_clients[device_id].discard(ws)
        if not _browser_clients[device_id]:
            del _browser_clients[device_id]

    if not sent:
        logger.warning(f"No WebSocket connections for device {device_id}")

    return sent


@devicetimer_websocket_router.websocket("/api/v1/ws/{device_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    device_id: str,
    type: Optional[str] = Query(default="hardware")
):
    """
    WebSocket endpoint for device connections.

    Query params:
        type: "hardware" (default) for ESP32 devices, "browser" for UI connections
    """
    await websocket.accept()

    # Select the appropriate client pool
    is_browser = type == "browser"
    clients = _browser_clients if is_browser else _hardware_clients
    client_type = "browser" if is_browser else "hardware"

    # Add to tracking
    if device_id not in clients:
        clients[device_id] = set()
    clients[device_id].add(websocket)

    logger.info(f"{client_type.capitalize()} connected for device {device_id}")

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received from {device_id} ({client_type}): {data}")
    except WebSocketDisconnect:
        logger.info(f"{client_type.capitalize()} disconnected for device {device_id}")
    except Exception as e:
        logger.debug(f"WebSocket error for {device_id}: {e}")
    finally:
        if device_id in clients:
            clients[device_id].discard(websocket)
            if not clients[device_id]:
                del clients[device_id]
        logger.debug(f"Connected hardware devices: {list(_hardware_clients.keys())}")


@devicetimer_websocket_router.get("/api/v1/ws/status")
async def get_websocket_status():
    """
    Return list of connected device IDs.
    Used by frontend to show real-time connection status.
    """
    return {"connected": get_connected_device_ids()}
