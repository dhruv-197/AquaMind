from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.security import get_current_user
from fastapi_app.database.connection import get_db
from fastapi_app.services.conversational_agent import water_copilot

router = APIRouter(prefix="/ai/copilot", tags=["AquaAI"], dependencies=[Depends(get_current_user)])


class HistoryTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    text: str = Field(..., min_length=1, max_length=4000)


class CopilotRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=700, description="User question")
    history: list[HistoryTurn] = Field(
        default_factory=list,
        description="Recent chat turns so follow-ups like 'give me a graph' keep context",
    )


@router.post("/chat", summary="AquaAI water-intelligence chat (grounded in live WSI)")
@limiter.limit("15/minute")
async def chat(request: Request, payload: CopilotRequest, db: Session = Depends(get_db)):
    try:
        history = [{"role": h.role, "text": h.text} for h in payload.history[-8:]]
        result = await water_copilot.answer(payload.message, db=db, history=history)
        return {"success": True, "data": result}
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Copilot request failed: {error}",
        )
