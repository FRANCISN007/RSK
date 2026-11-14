from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.models import User
from app.routers import auth, user, membership, admin, paper, free_game
from app.core.bootstrap import create_initial_admin
from app.routers import pool_season
from app.routers import pool_season, pool_week, admin_pool_season_cycles
from app.routers import discussions

Base.metadata.create_all(bind=engine)


create_initial_admin()

from fastapi.staticfiles import StaticFiles




app = FastAPI(
    title="Forecasting Platform API",
    description="API for the forecasting paper platform",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(user.router)
app.include_router(membership.router)
app.include_router(admin.router)
app.include_router(paper.router)
app.include_router(free_game.router)
app.include_router(pool_season.router)
app.include_router(pool_week.router)
app.include_router(admin_pool_season_cycles.router)
app.include_router(discussions.router)























@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Forecasting API is running",
    }



