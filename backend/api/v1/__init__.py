"""API v1 路由集合。"""

from fastapi import APIRouter

from backend.api.v1 import auth, tasks

router = APIRouter()
router.include_router(auth.router)
router.include_router(tasks.router)
