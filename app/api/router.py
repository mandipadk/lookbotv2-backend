from fastapi import APIRouter
from app.api.endpoints import auth, admin, watchlist, news, market_data

api_router = APIRouter()

# Auth routes
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

# Admin routes
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
)

# Watchlist routes (to be implemented)
api_router.include_router(
    watchlist.router,
    prefix="/watchlist",
    tags=["watchlist"]
)

# News routes (to be implemented)
api_router.include_router(
    news.router,
    prefix="/news",
    tags=["news"]
)

# Market data routes (to be implemented)
api_router.include_router(
    market_data.router,
    prefix="/market",
    tags=["market"]
)
