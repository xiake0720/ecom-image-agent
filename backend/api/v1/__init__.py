"""API v1 路由集合。"""

from fastapi import APIRouter

from backend.api.v1 import auth, image_edits, storage, tasks

router = APIRouter()
router.include_router(auth.router)
router.include_router(image_edits.router)
router.include_router(storage.router)
router.include_router(tasks.router)
