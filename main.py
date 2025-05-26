import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import uuid # For generating user IDs
from typing import Optional # For Optional query parameters
from datetime import datetime # For tournament creation timestamp
from fastapi import Form, HTTPException # For form data and error handling

# Import from our modules
from models import User, Tournament, TournamentCreate # Added Tournament, TournamentCreate
from json_utils import read_json_file, write_json_file, USERS_FILE, TOURNAMENTS_FILE # Added TOURNAMENTS_FILE


app = FastAPI()

templates = Jinja2Templates(directory="templates")


@app.get("/")
async def root():
    return {"message": "Tennis League API"}


# Simulated Google OAuth Endpoints
@app.get("/auth/google")
async def auth_google_redirect():
    # In a real scenario, this would redirect to Google's OAuth URL.
    # For now, simulate a successful auth by redirecting to callback
    # with dummy data.
    dummy_email = "testuser@example.com"
    dummy_name = "Test User"
    # In a real app, state and nonce would be used for security.
    return RedirectResponse(url=f"/auth/google/callback?email={dummy_email}&name={dummy_name}")


@app.get("/auth/google/callback")
async def auth_google_callback(email: str, name: Optional[str] = None):
    users_data = read_json_file(USERS_FILE)
    
    existing_user = next((u for u in users_data if u.get('email') == email), None)
    
    if not existing_user:
        new_user_id = str(uuid.uuid4())
        new_user = User(
            user_id=new_user_id,
            email=email,
            display_name=name if name else email.split('@')[0],
            google_id=None # Placeholder for actual Google ID
        )
        users_data.append(new_user.model_dump()) # Use .model_dump() for Pydantic v2+
        write_json_file(USERS_FILE, users_data)
        # print(f"New user created: {new_user.email}") # For debugging
    # else:
        # print(f"User logged in: {existing_user['email']}") # For debugging

    # For now, just redirect to tournaments page.
    # Session management will be added later.
    return RedirectResponse(url="/tournaments_page", status_code=303) # Use 303 for POST-redirect-GET


@app.post("/tournaments")
async def create_tournament(name: str = Form(...), format: str = Form(...)):
    users = read_json_file(USERS_FILE)
    admin_user_id = "default_admin_id" # Fallback admin_id

    if not users:
        # Create a default admin user if no user exists
        # This is for easier initial testing.
        default_admin = User(
            user_id=admin_user_id,
            email="admin@example.com",
            display_name="Default Admin",
            google_id="default_google_id" # Ensure all required fields are present
        )
        users.append(default_admin.model_dump())
        write_json_file(USERS_FILE, users)
        print(f"Created default admin user: {admin_user_id}") # For debugging
    else:
        # Use the first user as admin if users exist
        admin_user_id = users[0].get('user_id', admin_user_id) # Use .get for safety

    new_tournament_id = str(uuid.uuid4())
    invitation_code = str(uuid.uuid4())[:8].upper()

    tournament = Tournament(
        tournament_id=new_tournament_id,
        name=name,
        format=format,
        admin_user_id=admin_user_id,
        participants=[admin_user_id],
        invitation_code=invitation_code,
        matches=[],
        status="pending_setup",
        created_at=datetime.now()
    )

    tournaments_list = read_json_file(TOURNAMENTS_FILE)
    tournaments_list.append(tournament.model_dump(mode='json'))
    write_json_file(TOURNAMENTS_FILE, tournaments_list)
    
    return RedirectResponse(url="/tournaments_page", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/tournaments_page", response_class=HTMLResponse)
async def get_tournaments_page(request: Request):
    users = read_json_file(USERS_FILE)
    current_user_id = None
    current_user = None

    if users:
        # Simulate current user is the first user in the list
        # In a real app, this would come from session/token
        current_user = users[0] 
        current_user_id = current_user.get('user_id')
    else:
        # Fallback if no users exist (e.g., after initial setup or if users.json is empty)
        # This matches the fallback used in create_tournament if no users are present
        current_user_id = "default_admin_id" 
        # We could also pass a dummy User object for current_user if the template expects it
        # current_user = {"user_id": "default_admin_id", "display_name": "Guest"}


    all_tournaments_data = read_json_file(TOURNAMENTS_FILE)
    
    my_tournaments = []
    participated_tournaments = []

    if current_user_id:
        for tour_data in all_tournaments_data:
            # Data from JSON is dict. Access fields using string keys.
            if tour_data.get('admin_user_id') == current_user_id:
                my_tournaments.append(tour_data)
            elif current_user_id in tour_data.get('participants', []):
                # Avoid adding to participated if already an admin
                if tour_data.get('admin_user_id') != current_user_id:
                    participated_tournaments.append(tour_data)
            
    return templates.TemplateResponse("tournaments.html", {
        "request": request,
        "my_tournaments": my_tournaments,
        "participated_tournaments": participated_tournaments,
        "current_user": current_user # Pass the current_user object (or None) to the template
    })


@app.get("/create_tournament_page", response_class=HTMLResponse)
async def get_create_tournament_page(request: Request):
    return templates.TemplateResponse("create_tournaments.html", {"request": request})


@app.post("/tournaments/join")
async def join_tournament(invitation_code: str = Form(...)):
    users = read_json_file(USERS_FILE)
    if not users:
        # This scenario should ideally be prevented by requiring login first.
        # If login is simulated as creating a user, then this might not be hit often.
        raise HTTPException(status_code=403, detail="No user available to join a tournament. Please 'login' first.")
    
    # Simulate current user is the first user in the list
    current_user_id = users[0].get('user_id')
    if not current_user_id:
        # Handle cases where the user object might be malformed or missing user_id
        raise HTTPException(status_code=500, detail="User data is invalid.")

    tournaments_list = read_json_file(TOURNAMENTS_FILE)
    tournament_found = False
    for i, tour_data in enumerate(tournaments_list):
        if tour_data.get('invitation_code') == invitation_code:
            tournament_found = True
            
            # Check if user is the admin
            if tour_data.get('admin_user_id') == current_user_id:
                # Admin is implicitly a participant. Redirect with a message.
                # Using query params for messages can be simple for server-rendered pages.
                return RedirectResponse(url="/tournaments_page?message=Admin is already part of this tournament", status_code=303)
            
            # Check if user is already a participant
            if current_user_id in tour_data.get('participants', []):
                return RedirectResponse(url="/tournaments_page?message=Already a participant in this tournament", status_code=303)
            
            # Add user to participants list
            # Ensure 'participants' list exists, though it should by model definition
            if 'participants' not in tournaments_list[i] or tournaments_list[i]['participants'] is None:
                 tournaments_list[i]['participants'] = [] # Initialize if missing, though unlikely with Pydantic
            
            tournaments_list[i]['participants'].append(current_user_id)
            write_json_file(TOURNAMENTS_FILE, tournaments_list)
            return RedirectResponse(url="/tournaments_page?message=Successfully joined tournament", status_code=303)
    
    if not tournament_found:
        # If code not found, redirect with error message or raise HTTPException
        # Raising an exception might be better for API consistency,
        # but for web flow, redirecting with a message can be user-friendlier.
        # The example uses HTTPException, so we'll stick to that for now.
        raise HTTPException(status_code=404, detail=f"Tournament with invitation code '{invitation_code}' not found.")

    # Fallback redirect, though logic above should cover all paths.
    # This line might be unreachable if all cases are handled with redirects/exceptions.
    return RedirectResponse(url="/tournaments_page", status_code=303)


@app.get("/tournaments/{tournament_id}/bracket", response_class=HTMLResponse)
async def get_tournament_bracket(tournament_id: str, request: Request):
    tournaments_list = read_json_file(TOURNAMENTS_FILE)
    tournament_data = next((t for t in tournaments_list if t.get('tournament_id') == tournament_id), None)

    if not tournament_data:
        raise HTTPException(status_code=404, detail="Tournament not found")

    participants = tournament_data.get('participants', [])
    # In a real scenario, users_data would be read to get display names
    # For now, we'll just use the IDs or a placeholder.
    # Let's try to read user data to display names if possible, falling back to IDs
    users_list = read_json_file(USERS_FILE)
    participant_names = []
    for p_id in participants:
        user = next((u for u in users_list if u.get('user_id') == p_id), None)
        if user:
            participant_names.append(user.get('display_name', f"User_{p_id[:6]}"))
        else:
            participant_names.append(f"User_{p_id[:6]}")


    bracket_html = f"<h1>Bracket for {tournament_data.get('name')}</h1>"
    bracket_html += "<p>Bracket generation is under development. Matches will be displayed here.</p>"
    bracket_html += "<h2>Participants:</h2><ul>"
    for p_name in participant_names:
        bracket_html += f"<li>{p_name}</li>"
    bracket_html += "</ul>"
    bracket_html += '<p><a href="/tournaments_page">Back to Tournaments</a></p>'
    
    return HTMLResponse(content=bracket_html)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
