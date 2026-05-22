from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.auth import verify_api_token
from src.api.schemas import ApiResponse
from src.database import DatabaseManager

router = APIRouter(prefix='/v1/notifications', tags=['notifications'])
_db = DatabaseManager()


class DeliverRequest(BaseModel):
    wxid: str
    ids: List[int]


@router.get('/pending', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def pending(wxid: str = Query(...), limit: int = Query(3, ge=1, le=10)):
    rows = _db.get_pending_notifications(wxid, limit=limit)
    if not rows:
        return ApiResponse(success=True, message='', data={'items': []})

    items = [dict(row) for row in rows]
    parts = [item['message'] for item in items]
    combined = '\n\n'.join(parts)
    return ApiResponse(
        success=True,
        message=combined,
        data={'items': items, 'ids': [item['id'] for item in items]},
    )


@router.post('/deliver', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def deliver(body: DeliverRequest):
    if body.ids:
        _db.mark_notifications_delivered(body.ids)
    return ApiResponse(success=True, message='ok')
