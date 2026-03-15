from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.api.schemas.chat import ChatSessionSummary


router = APIRouter(tags=["sessions"])


@router.get("/sessions/{session_id}", response_model=ChatSessionSummary)
def get_session(
    session_id: str,
    request: Request,
    session_access_token: str = Query(min_length=1),
) -> ChatSessionSummary:
    session = request.app.state.session_store.get_session_by_access_token(session_id, session_access_token)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return ChatSessionSummary.model_validate(session.to_summary())
