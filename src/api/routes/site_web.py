import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=['site'])

_STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'site')


@router.get('/')
async def site_home():
    index_path = os.path.join(_STATIC_DIR, 'index.html')
    return FileResponse(index_path, media_type='text/html; charset=utf-8')
