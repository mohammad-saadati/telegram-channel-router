from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.integrations.telegram import TelegramAPIError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/telegram")
async def telegram_health(container: ContainerDep) -> dict[str, object]:
    try:
        me = await container.telegram.get_me()
    except TelegramAPIError as exc:
        return {"status": "error", "detail": exc.description}
    return {"status": "ok", "bot": me.get("username")}
