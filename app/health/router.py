from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Check application health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
