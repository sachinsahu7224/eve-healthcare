from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.bookings import router as bookings_router
from app.api.routes.centres import router as centres_router
from app.api.routes.payments import router as payments_router
from app.api.routes.tests import router as tests_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(centres_router)
api_router.include_router(tests_router)
api_router.include_router(bookings_router)
api_router.include_router(payments_router)

__all__ = ["api_router"]
