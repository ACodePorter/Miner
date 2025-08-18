"""API v1 router with all endpoints organized by functionality"""

from fastapi import APIRouter

from .data import router as data_router
from .diagnostics import router as diagnostics_router
from .market_data import router as market_data_router
from .tasks import router as tasks_router
from .watchlist import router as watchlist_router
from .websocket import router as websocket_router

# Create main v1 API router
api_v1_router = APIRouter(prefix="/api/v1", tags=["api-v1"])

# Include all sub-routers
api_v1_router.include_router(websocket_router)
api_v1_router.include_router(market_data_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(diagnostics_router)
api_v1_router.include_router(data_router)
api_v1_router.include_router(watchlist_router)
