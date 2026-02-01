from __future__ import annotations

import httpx
from .config import GUVI_CALLBACK_URL
from .models import FinalCallbackPayload


async def send_final_callback(payload: FinalCallbackPayload) -> None:
    """
    Best-effort callback. We keep it async so /v1/message stays fast.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        for _ in range(3):
            try:
                r = await client.post(GUVI_CALLBACK_URL, json=payload.model_dump())
                if 200 <= r.status_code < 300:
                    return
            except Exception:
                pass
