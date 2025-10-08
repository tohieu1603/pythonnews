"""Main router file cho notification app - tập hợp tất cả các sub-routers"""
from ninja import Router

from apps.notification.routers.endpoint_router import router as endpoint_router
from apps.notification.routers.event_router import router as event_router
from apps.notification.routers.webhook_router import router as webhook_router

router = Router(tags=["notifications"])

router.add_router("", endpoint_router)
router.add_router("", event_router)
router.add_router("", webhook_router)
