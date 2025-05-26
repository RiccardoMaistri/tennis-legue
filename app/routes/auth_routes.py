from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth # Already imported in main.py, but good for clarity
from app.services.user_service import UserService
from app.models.user_model import UserModel
import uuid # For session state

# This assumes 'oauth' and 'user_service' are initialized in main.py and accessible.
# For a cleaner approach, especially with testing, dependency injection or app state might be better.
# However, for this structure, we'll rely on them being available via the app instance or global scope.
# A common way is to get them from the request.app.state if configured there.

# Let's assume main.py looks like this for context:
# from fastapi import FastAPI
# from starlette.middleware.sessions import SessionMiddleware
# from authlib.integrations.starlette_client import OAuth
# from app.services.user_service import UserService
#
# app = FastAPI()
# app.add_middleware(SessionMiddleware, secret_key="YOUR_SECRET_KEY")
# oauth = OAuth(app) # or just oauth = OAuth() if not passing app
# oauth.register(...)
# user_service = UserService()
#
# from app.routes import auth_routes
# app.include_router(auth_routes.router, prefix="/auth")


router = APIRouter()

# Dependency to get oauth and user_service from request.app.state
# This is a placeholder, actual setup in main.py is needed.
def get_oauth_client(request: Request) -> OAuth:
    # In a real app, you'd likely attach 'oauth' to app.state in main.py
    # e.g., app.state.oauth = oauth
    # For now, we'll access the global 'oauth' from main.py (requires careful import order or passing)
    from app.main import oauth as global_oauth
    return global_oauth

def get_user_service(request: Request) -> UserService:
    from app.main import user_service as global_user_service
    return global_user_service


@router.get("/login/google", summary="Initiate Google OAuth2 login")
async def login_google(request: Request, oauth_client: OAuth = Depends(get_oauth_client)):
    """
    Redirects the user to Google's OAuth2 authorization page.
    A unique `state` parameter is generated and stored in the session for CSRF protection.
    Upon successful authorization, Google will redirect the user back to the `/auth/google/callback` endpoint.
    """
    redirect_uri = request.url_for('auth_google_callback')
    # Generate a unique state for CSRF protection
    state = str(uuid.uuid4())
    request.session['oauth_state'] = state
    return await oauth_client.google.authorize_redirect(request, redirect_uri, state=state)


@router.get("/google/callback", name="auth_google_callback", summary="Handle Google OAuth2 callback")
async def auth_google_callback(request: Request, oauth_client: OAuth = Depends(get_oauth_client), user_service: UserService = Depends(get_user_service)):
    """
    Handles the callback from Google after the user has authorized the application.
    It verifies the `state` parameter for CSRF protection, fetches the access token,
    retrieves user information from Google, and then creates or updates the user
    in the local database. Finally, it establishes a session for the authenticated user.
    """
    # Check state for CSRF protection
    expected_state = request.session.pop('oauth_state', None)
    received_state = request.query_params.get('state')

    if not expected_state or expected_state != received_state:
        raise HTTPException(status_code=401, detail="Invalid OAuth state")

    try:
        token = await oauth_client.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Could not authorize access token: {str(e)}")

    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(status_code=401, detail="Could not fetch user info from Google.")

    oauth_provider = "google"
    oauth_provider_id = user_info.get("sub") # 'sub' is the standard OpenID Connect subject identifier
    email = user_info.get("email")
    full_name = user_info.get("name")

    if not email or not oauth_provider_id:
        raise HTTPException(status_code=400, detail="Email or Google User ID not found in token.")

    # Check if user exists by OAuth ID
    user = user_service.get_user_by_oauth_id(provider=oauth_provider, oauth_id=oauth_provider_id)

    if not user:
        # If not, check by email (user might have logged in via another method before)
        user = user_service.get_user_by_email(email=email)
        if user:
            # Link OAuth account if found by email but not by OAuth ID (e.g. first time Google login for existing email)
            # For this example, we'll assume if email matches, it's the same user.
            # In a real app, you might want to confirm this or handle conflicts.
            user.oauth_provider = oauth_provider
            user.oauth_provider_id = oauth_provider_id
            # Here we would typically update the user in the DB.
            # Since our user_service doesn't have an update method yet, we'll skip for now
            # or re-create (which is not ideal).
            # For simplicity, if found by email but not oauth_id, we'll treat as existing and linked.
            pass # Assuming user_service.update_user(user) would be called here
        else:
            # If user doesn't exist at all, create them
            user_data = UserModel(
                email=email,
                full_name=full_name,
                oauth_provider=oauth_provider,
                oauth_provider_id=oauth_provider_id
            )
            try:
                user = user_service.create_user(user_data)
            except ValueError as e: # Handles duplicate email from create_user
                raise HTTPException(status_code=409, detail=str(e))


    # Store user ID or essential info in session
    request.session["user_id"] = user.id
    request.session["user_email"] = user.email # Optional, for convenience

    return JSONResponse(content={"message": "Successfully authenticated with Google.", "user_email": user.email, "user_id": user.id})


@router.get("/logout", summary="Log out the current user")
async def logout(request: Request):
    """
    Clears the current user's session, effectively logging them out.
    """
    request.session.clear()
    return JSONResponse(content={"message": "Successfully logged out."})


@router.get("/me", summary="Get current authenticated user details")
async def me(request: Request, user_service: UserService = Depends(get_user_service)):
    """
    Retrieves and returns the details of the currently authenticated user
    based on the active session. If no user is authenticated, a 401 error is returned.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # In a real app, you'd load the user from UserService using user_id
    # For now, our UserService doesn't have get_user_by_id. We can add it or just return session data.
    # Let's assume we'll add get_user_by_id to UserService later.
    # For now, returning what's in session.
    user_email = request.session.get("user_email")
    
    # Placeholder: Fetch full user details if needed
    # user = user_service.get_user_by_id(user_id) # Assuming this method exists
    # if not user:
    #     raise HTTPException(status_code=404, detail="User not found")
    # return user

    return JSONResponse(content={"user_id": user_id, "email": user_email, "message": "Authenticated user details."})
