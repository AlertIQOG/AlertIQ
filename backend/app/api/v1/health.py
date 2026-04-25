from fastapi import APIRouter

router = APIRouter()


@router.get("", summary="Health Check")
async def health():
    """Returns the current health status of the service."""
    return {"status": "healthy"}
