from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from app.services.user_service import UserService
from app.models.user_model import UserModel # Though not directly used in main.py, good for context

# Configuration - Replace with your actual credentials and secret key
GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"
SESSION_SECRET_KEY = "YOUR_SECRET_KEY" # For SessionMiddleware

app = FastAPI()

# Add SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# Initialize OAuth client
oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Instantiate UserService
user_service = UserService()

# Import and include auth routes
from app.routes import auth_routes
app.include_router(auth_routes.router, prefix="/auth", tags=["Authentication"])

# Import and include tournament routes
from app.routes import tournament_routes
app.include_router(tournament_routes.router, prefix="/api/tournaments", tags=["Tournaments"])


@app.get("/ping")
async def ping():
    return {"ping": "pong"}
