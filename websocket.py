"""
WebSocket management for DeviceTimer extension.

Handles device connections and message broadcasting.
Tracks connected devices to show real-time status in UI.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from typing import Dict, Set

devicetimer_websocket_router = APIRouter()

# Track connected devices: device_id -> set of WebSocket connections
# Multiple connections per device are supported (e.g., multiple browser tabs)
_connected_clients: Dict[str, Set[WebSocket]] = {}


def get_connected_device_ids() -> list[str]:
    """Return list of device IDs with active WebSocket connections."""
    return list(_connected_clients.keys())


def is_device_connected(device_id: str) -> bool:
    """Check if a device has any active WebSocket connections."""
    return device_id in _connected_clients and len(_connected_clients[device_id]) > 0


async def send_to_device(device_id: str, message: str) -> bool:
    """
    Send a message to all WebSocket connections for a device.
    Returns True if message was sent to at least one client.
    """
    if device_id not in _connected_clients:
        logger.warning(f"No WebSocket connections for device {device_id}")
        return False

    sent = False
    dead_connections: Set[WebSocket] = set()

    for websocket in _connected_clients[device_id]:
        try:
            await websocket.send_text(message)
            sent = True
        except Exception as e:
            logger.debug(f"Failed to send to WebSocket: {e}")
            dead_connections.add(websocket)

    # Clean up dead connections
    for ws in dead_connections:
        _connected_clients[device_id].discard(ws)

    # Remove device entry if no connections left
    if device_id in _connected_clients and not _connected_clients[device_id]:
        del _connected_clients[device_id]

    return sent


@devicetimer_websocket_router.websocket("/api/v1/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    """
    WebSocket endpoint for device connections.
    Hardware devices connect here to receive payment notifications.
    """
    await websocket.accept()

    # Add to tracking
    if device_id not in _connected_clients:
        _connected_clients[device_id] = set()
    _connected_clients[device_id].add(websocket)

    logger.info(f"Device {device_id} connected. Total connections: {len(_connected_clients[device_id])}")

    try:
        while True:
            # Keep connection alive, wait for messages (ping/pong handled automatically)
            data = await websocket.receive_text()
            # Hardware might send status updates, we just acknowledge
            logger.debug(f"Received from {device_id}: {data}")
    except WebSocketDisconnect:
        logger.info(f"Device {device_id} disconnected")
    except Exception as e:
        logger.debug(f"WebSocket error for {device_id}: {e}")
    finally:
        # Remove from tracking
        if device_id in _connected_clients:
            _connected_clients[device_id].discard(websocket)
            if not _connected_clients[device_id]:
                del _connected_clients[device_id]
        logger.info(f"Device {device_id} cleaned up. Connected devices: {list(_connected_clients.keys())}")


@devicetimer_websocket_router.get("/api/v1/ws/status")
async def get_websocket_status():
    """
    Return list of connected device IDs.
    Used by frontend to show real-time connection status.
    """
    return {"connected": get_connected_device_ids()}
