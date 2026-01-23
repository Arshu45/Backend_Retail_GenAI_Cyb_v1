"""Router for session management."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from src.interfaces.api.dependencies import get_agent_service
from src.application.services.agent_service import AgentService

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("", response_model=Dict[str, str])
async def create_session(
    agent_service: AgentService = Depends(get_agent_service)
) -> Dict[str, str]:
    """Create a new session with a unique UUID."""
    session_id = agent_service.create_session()
    return {"session_id": session_id}

@router.get("", response_model=List[str])
async def list_sessions(
    agent_service: AgentService = Depends(get_agent_service)
) -> List[str]:
    """List all active session IDs."""
    return agent_service.get_all_sessions()

@router.get("/{session_id}/history", response_model=List[Dict[str, Any]])
async def get_session_history(
    session_id: str,
    agent_service: AgentService = Depends(get_agent_service)
) -> List[Dict[str, Any]]:
    """Get chat history for a specific session."""
    history = agent_service.get_session_history(session_id)
    if not history and session_id not in agent_service.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return history

@router.delete("/{session_id}")
async def reset_session(
    session_id: str,
    agent_service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    """Reset/Clear a specific session."""
    success = agent_service.reset_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "message": f"Session {session_id} reset successfully"}

@router.delete("")
async def clear_all_sessions(
    agent_service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    """Clear all active sessions."""
    session_ids = agent_service.get_all_sessions()
    for sid in session_ids:
        agent_service.reset_session(sid)
    return {"success": True, "message": f"Cleared {len(session_ids)} sessions"}
