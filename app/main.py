from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse # Added for serving HTML

from app.api.endpoints import auth as auth_endpoints
from app.api.endpoints import users as user_endpoints
from app.api.endpoints import tournaments as tournament_endpoints
from app.api.endpoints import matches as match_endpoints
from app.api.endpoints import notifications as notification_endpoints
from app.core.database import engine #, SessionLocal # SessionLocal might not be needed directly here
from app.models import Base # If Base.metadata.create_all is in models.__init__

# If Base.metadata.create_all is in app.models.__init__.py, it runs when models are imported.
# For explicit control or if not done in __init__.py:
# Base.metadata.create_all(bind=engine)
# Alternatively, ensure models are imported so their __init__ runs:
import app.models # This will trigger Base.metadata.create_all(bind=engine) if it's in app/models/__init__.py

app = FastAPI(title="Tennis Tournament API")

# Mount static files first
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(auth_endpoints.router, prefix="/auth", tags=["Authentication"])
app.include_router(user_endpoints.router, prefix="/users", tags=["Users"])
app.include_router(tournament_endpoints.router, prefix="/tournaments", tags=["Tournaments"])
app.include_router(match_endpoints.router, prefix="/matches", tags=["Matches"])
app.include_router(notification_endpoints.router, prefix="/notifications", tags=["Notifications"])


@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Serve login.html as the root page for now
    return FileResponse("app/static/login.html")

# Example of how to ensure tables are created (if not done in models.__init__)

# Example of how to ensure tables are created (if not done in models.__init__)
# @app.on_event("startup")
# async def startup_event():
#     Base.metadata.create_all(bind=engine)
