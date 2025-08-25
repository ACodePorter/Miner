import json
import logging
from datetime import datetime
from typing import Any, Dict

from detonator import get_logger
from fastapi import WebSocket

_l = get_logger('Utils', logging.DEBUG)


async def send_message(websocket: WebSocket, client_id: str, type: str, message: Dict[str, Any]):
    try:
        d = message.copy()
        d['type'] = type
        d['timestamp']: datetime.now().isoformat()
        _l.debug(f"{client_id} <- {json.dumps(d)}")
        await websocket.send_text(json.dumps(d))
    except Exception as e:
        _l.error(f"{client_id} <- {e}")
        raise Exception(f'Failed to send {message} to {client_id}') from e
