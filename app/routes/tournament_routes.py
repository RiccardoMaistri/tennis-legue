from fastapi import APIRouter, Depends, HTTPException, Request, Body, Path
from typing import List, Optional # Added Optional
from datetime import datetime # Added datetime for DTOs
from pydantic import BaseModel, Field # Added for DTOs

from app.services.tournament_service import TournamentService
from app.models.tournament_model import TournamentConfig, TournamentType
# from app.models.user_model import UserModel # Not directly used for response model here
# from app.services.user_service import UserService # Not strictly needed for these endpoints

router = APIRouter()
tournament_service = TournamentService() # Instantiated service

# --- Authentication and Authorization Dependencies ---

async def get_current_user_id(request: Request) -> str:
    """
    Retrieves user_id from session.
    Raises HTTPException if user is not authenticated.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id

async def get_tournament_if_admin(
    tournament_id: str = Path(..., description="The ID of the tournament"),
    current_user_id: str = Depends(get_current_user_id),
    service: TournamentService = Depends(lambda: tournament_service) # Use a lambda to pass the instance
) -> TournamentConfig:
    """
    Dependency to get a tournament and verify if the current user is its admin.
    Raises HTTPException if tournament not found or user is not admin.
    """
    tournament = service.get_tournament_by_id(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if tournament.admin_id != current_user_id:
        raise HTTPException(status_code=403, detail="User is not authorized to perform this action on this tournament")
    return tournament

# --- DTOs (Data Transfer Objects) for request bodies ---

class TournamentCreationRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="Name of the tournament")
    tournament_type: TournamentType = Field(..., description="Type of the tournament")
    start_date: Optional[datetime] = Field(None, description="Optional start date of the tournament")
    end_date: Optional[datetime] = Field(None, description="Optional end date of the tournament")
    # admin_id will be set from current_user_id
    # player_ids will default to empty list
    # status will default to "PENDING" (handled by TournamentConfig model)

class AddPlayerRequest(BaseModel):
    """Payload for adding a player to a tournament."""
    player_id: str = Field(..., description="User ID of the player to add.")

class UpdateStatusRequest(BaseModel):
    """Payload for updating the status of a tournament."""
    status: str = Field(..., description="New status for the tournament (e.g., REGISTRATION_OPEN, ACTIVE, COMPLETED).")


# --- Tournament Endpoints ---

@router.post("", response_model=TournamentConfig, status_code=201, summary="Create New Tournament")
async def create_tournament(
    tournament_data: TournamentCreationRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Creates a new tournament with the authenticated user as its admin.

    - **name**: Name of the tournament (must be 3-100 characters).
    - **tournament_type**: Specifies the format (e.g., SINGLE_ELIMINATION, ROUND_ROBIN).
    - **start_date** (optional): The planned start date and time for the tournament.
    - **end_date** (optional): The planned end date and time. Must be later than the start_date if both are provided.
    """
    config_data_dict = tournament_data.model_dump()
    config_data_dict["admin_id"] = current_user_id
    
    # Create TournamentConfig instance, this will also validate using Pydantic model rules
    try:
        tournament_config = TournamentConfig(**config_data_dict)
    except ValueError as e: # Pydantic validation error
        raise HTTPException(status_code=422, detail=str(e)) # Unprocessable Entity

    try:
        created_config = service.create_tournament(tournament_config)
        return created_config
    except ValueError as e: # Custom validation from service (e.g. duplicate name for admin)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# --- Bracket Generation Endpoint ---
from app.models.bracket_model import BracketModel # For response model
from app.services.bracket_service import BracketService # Import BracketService

bracket_service_instance = BracketService() # Instantiate BracketService

@router.post("/{tournament_id}/generate-bracket", response_model=BracketModel, summary="Generate bracket for the tournament")
async def generate_tournament_bracket(
    tournament_id: str = Path(..., description="The ID of the tournament"),
    current_tournament: TournamentConfig = Depends(get_tournament_if_admin), # Ensures user is admin
    # bracket_service: BracketService = Depends(lambda: bracket_service_instance) # Pass service instance
):
    """
    Generates the bracket for the specified tournament.
    Only the tournament admin can perform this action.
    This will typically change the tournament status to "ACTIVE".
    If a bracket already exists and the tournament is active/completed, it might return the existing one or prevent regeneration.
    """
    # The get_tournament_if_admin dependency already verifies admin and fetches the tournament.
    # current_tournament.id is the validated tournament_id.
    
    # Check if tournament status allows bracket generation
    # Typically, generate bracket if status is PENDING or REGISTRATION_OPEN.
    # The service method create_bracket_for_tournament handles this logic.
    # if current_tournament.status not in ["PENDING", "REGISTRATION_OPEN"]:
    #     raise HTTPException(status_code=400, detail=f"Bracket cannot be generated for tournament with status '{current_tournament.status}'.")

    try:
        # Using the globally instantiated bracket_service_instance for now
        bracket = bracket_service_instance.create_bracket_for_tournament(current_tournament.id)
        if not bracket:
            # This might happen if generation fails for an unexpected reason not caught by specific errors.
            raise HTTPException(status_code=500, detail="Bracket generation failed.")
        return bracket
    except ValueError as e: # Catch errors like "Tournament has no players", "Tournament not found"
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e: # If bracket type is not supported
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        # Log the exception for debugging
        print(f"Unexpected error during bracket generation: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during bracket generation: {str(e)}")

# --- Match Result Endpoint ---
from app.models.bracket_model import MatchModel # For response model for match result

class MatchResultPayload(BaseModel):
    score_player1: int = Field(..., ge=0, description="Score for player 1")
    score_player2: int = Field(..., ge=0, description="Score for player 2")

@router.post("/{tournament_id}/matches/{match_id}/result", response_model=MatchModel, summary="Record the result of a match")
async def record_match_result_endpoint(
    tournament_id: str = Path(..., description="The ID of the tournament"),
    match_id: str = Path(..., description="The ID of the match"),
    payload: MatchResultPayload,
    current_user_id: str = Depends(get_current_user_id), # Ensures user is logged in
    # BracketService instance is already available as bracket_service_instance
):
    """
    Record the result for a specific match within a tournament.
    Only the tournament admin can perform this action.
    - **score_player1**: Score achieved by player 1.
    - **score_player2**: Score achieved by player 2.
    In single-elimination, scores typically cannot be equal.
    """
    try:
        updated_match = bracket_service_instance.record_match_result(
            tournament_id=tournament_id,
            match_id=match_id,
            p1_score=payload.score_player1,
            p2_score=payload.score_player2,
            current_user_id=current_user_id
        )
        if not updated_match:
            # This case might occur if the service returns None for a reason not covered by exceptions
            # (e.g., match found but somehow not updated, though current service raises errors).
            raise HTTPException(status_code=400, detail="Failed to record match result.")
        return updated_match
    except ValueError as e: # Covers match not found, tournament not found, invalid scores, match not updatable
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e: # For authorization failure
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        # Log the exception for debugging
        print(f"Unexpected error recording match result: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("", response_model=List[TournamentConfig], summary="List User's Administered Tournaments")
async def list_admin_tournaments(
    current_user_id: str = Depends(get_current_user_id),
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Retrieves a list of all tournaments for which the currently authenticated user is the administrator.
    """
    return service.get_tournaments_by_admin(admin_id=current_user_id)


@router.get("/all", response_model=List[TournamentConfig], summary="List All Public Tournaments")
async def list_all_tournaments(
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Fetches a list of all tournaments. This endpoint is publicly accessible and can be used
    by any user to browse available tournaments.
    """
    return service.get_all_tournaments()


@router.get("/{tournament_id}", response_model=TournamentConfig, summary="Get Specific Tournament Details")
async def get_specific_tournament(
    tournament_id: str = Path(..., description="The ID of the tournament to retrieve."),
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Retrieves detailed information about a specific tournament identified by its ID.
    This endpoint is publicly accessible.
    """
    tournament = service.get_tournament_by_id(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return tournament


@router.post("/{tournament_id}/players", response_model=TournamentConfig, summary="Add Player to Tournament (Admin Only)")
async def add_player_to_tournament_route(
    player_data: AddPlayerRequest,
    tournament_id: str = Path(..., description="The ID of the tournament to add a player to."),
    current_tournament: TournamentConfig = Depends(get_tournament_if_admin), # Ensures user is admin & tournament exists
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Adds a player to a specific tournament.
    This action can only be performed by the tournament administrator.
    The request body should contain the `player_id` of the user to be added.
    """
    try:
        # current_tournament is already verified and fetched by the dependency
        updated_tournament = service.add_player_to_tournament(current_tournament.id, player_data.player_id)
        if not updated_tournament:
            # This might occur if the player_id is invalid or some other logic prevents addition,
            # though the service method might raise ValueError for known issues.
            # Or if tournament somehow disappeared, though get_tournament_if_admin should prevent this.
            raise HTTPException(status_code=400, detail="Failed to add player to tournament.")
        return updated_tournament
    except ValueError as e: # Catches errors like "Player already in tournament" or status restrictions
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.patch("/{tournament_id}/status", response_model=TournamentConfig, summary="Update Tournament Status (Admin Only)")
async def update_tournament_status_route(
    status_data: UpdateStatusRequest,
    tournament_id: str = Path(..., description="The ID of the tournament whose status is to be updated."),
    current_tournament: TournamentConfig = Depends(get_tournament_if_admin), # Ensures user is admin & tournament exists
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Updates the status of a specific tournament (e.g., from PENDING to REGISTRATION_OPEN, or ACTIVE to COMPLETED).
    This action can only be performed by the tournament administrator.
    The request body must contain the new valid `status`.
    """
    try:
        # current_tournament is already verified
        updated_tournament = service.update_tournament_status(current_tournament.id, status_data.status)
        if not updated_tournament:
            # Should be caught by service if tournament disappears, or by dependency.
            raise HTTPException(status_code=404, detail="Tournament not found during status update.")
        return updated_tournament
    except ValueError as e: # Catches invalid status from service (which uses model validation)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete("/{tournament_id}", status_code=204, summary="Delete Tournament (Admin Only)")
async def delete_tournament_route(
    tournament_id: str = Path(..., description="The ID of the tournament to be deleted."),
    current_user_id: str = Depends(get_current_user_id), # Need current user to pass to service for admin check
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Deletes a tournament. This action can only be performed by the tournament administrator.
    Deletion might be restricted based on the tournament's status (e.g., active or completed tournaments).
    A successful deletion returns a 204 No Content response.
    """
    try:
        # The service's delete_tournament method should verify admin_id.
        # We pass current_user_id to it for this purpose.
        # The get_tournament_if_admin dependency is not used here because it would fetch the tournament,
        # which might be redundant if the delete operation handles the check and deletion in one go.
        # However, for consistency, one might prefer to use it and then call delete.
        # Let's adjust to use the service layer check directly.
        success = service.delete_tournament(tournament_id=tournament_id, admin_id=current_user_id)
        if not success:
            # This could mean tournament not found or user not admin, service should raise specific errors.
            # If service returns False without raising, we assume a generic failure.
            raise HTTPException(status_code=400, detail="Failed to delete tournament. It might not exist or you are not the admin.")
    except ValueError as e: # E.g., "Tournament not found" or "Cannot delete active tournament"
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e: # If service raises PermissionError for auth failure
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    
    return None # FastAPI will return 204 No Content for None body with status_code=204


# --- Tournament Invitation Endpoints ---

class InviteLinkResponse(BaseModel):
    invite_link: str = Field(description="The full invite link URL that users can use to join the tournament.")
    tournament_name: str = Field(description="The name of the tournament for which the invite link is generated.")
    invite_token: str = Field(description="The unique token embedded in the invite link.")

@router.post("/{tournament_id}/invite-link", response_model=InviteLinkResponse, summary="Get/Generate Invite Link (Admin Only)")
async def generate_tournament_invite_link(
    request: Request, # To construct the full URL
    tournament_id: str = Path(..., description="The ID of the tournament for which to generate an invite link."),
    current_tournament: TournamentConfig = Depends(get_tournament_if_admin), # Ensures user is admin
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Generates or retrieves an existing invite link for the specified tournament.
    This action can only be performed by the tournament administrator.
    The response includes the full invite link, tournament name, and the raw invite token.
    """
    try:
        # The get_tournament_if_admin dependency already verified admin and fetched the tournament.
        # Now, ensure the token generation/retrieval logic is called.
        # The service method handles whether to generate a new token or return existing.
        updated_tournament = service.generate_invite_token(tournament_id=current_tournament.id, admin_id=current_tournament.admin_id)

        if not updated_tournament or not updated_tournament.invite_token:
            raise HTTPException(status_code=500, detail="Failed to generate or retrieve invite token.")

        # Construct the full invite link URL
        # Example: http://localhost:8000/api/tournaments/join/YOUR_TOKEN_HERE
        # Note: The prefix "/api/tournaments" is already part of this router.
        # We need the base URL and then the specific path for joining.
        join_path = router.url_path_for("join_tournament_by_link", invite_token=updated_tournament.invite_token)
        # request.base_url gives something like http://localhost:8000/
        # We need to be careful with slashes.
        # router.prefix is /api/tournaments
        # So, the full URL should be request.base_url + app.url_path_for('join_tournament_by_link', invite_token=...)
        # However, url_path_for on a router already considers its prefix if the route is part of it.
        # For a route defined globally in the app, you'd use request.app.url_path_for.
        
        # A simpler way to ensure correctness for this structure:
        # The join endpoint will be /api/tournaments/join/{invite_token}
        # So, base_url + "api/tournaments/join/" + token
        
        # Using request.url_for which is generally safer for generating URLs within the app
        # Ensure the "join_tournament_by_link" route has a 'name' attribute.
        base_url = str(request.base_url).rstrip('/')
        # The route for joining is within the same router, so its path is relative to the router's prefix.
        # The prefix /api/tournaments is handled by the main app when including the router.
        # So, request.url_for('join_tournament_by_link', invite_token=...) should generate the path *after* the prefix.
        # Correct path construction needs care.
        # Let's assume the "join_tournament_by_link" endpoint is defined with name="join_tournament_by_link"
        
        # Path for the join endpoint, relative to the application root
        # The router prefix will be automatically handled by FastAPI's URL generation.
        # The route name must match the one defined for the join endpoint.
        # join_url_path = request.app.url_path_for("join_tournament_by_link", invite_token=updated_tournament.invite_token)
        # full_invite_link = f"{base_url}{join_url_path}"
        
        # For now, let's construct it manually, assuming the frontend or user knows the base path.
        # The key part is providing the token.
        # A more robust way:
        # join_url = request.url_for('join_tournament_by_link', invite_token=updated_tournament.invite_token)
        # This will give a path like /api/tournaments/join/TOKEN if the named route is found.
        # If the join route is named 'join_tournament_by_link':
        # full_invite_link = str(request.url_for('join_tournament_by_link', invite_token=updated_tournament.invite_token))
        # This usually gives a relative path. For a full URL:
        full_invite_link = f"{base_url}{router.prefix}/join/{updated_tournament.invite_token}"


        return InviteLinkResponse(
            invite_link=full_invite_link,
            tournament_name=updated_tournament.name,
            invite_token=updated_tournament.invite_token
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e: # E.g., tournament not found by service
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.post("/join/{invite_token}", response_model=TournamentConfig, summary="Join Tournament via Invite Token")
async def join_tournament_by_link(
    invite_token: str = Path(..., description="The unique invite token for joining the tournament."),
    current_user_id: str = Depends(get_current_user_id), # User must be authenticated to join
    service: TournamentService = Depends(lambda: tournament_service)
):
    """
    Allows an authenticated user to join a tournament by providing a valid invite token.
    The user will be added to the tournament's player list if the token is valid and
    the tournament is open for registration.
    """
    try:
        updated_tournament = service.join_tournament_with_token(token=invite_token, user_id=current_user_id)
        if not updated_tournament:
            # This case might be if the token is valid but user somehow couldn't be added,
            # though service method should raise ValueError for most issues.
            raise HTTPException(status_code=400, detail="Failed to join tournament. Invalid token or user already joined.")
        return updated_tournament
    except ValueError as e: # Catches "Invalid or expired invite token", "User already in tournament", status restrictions
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e: # Catches consistency errors from service
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
