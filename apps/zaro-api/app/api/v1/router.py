from fastapi import APIRouter

from app.api.v1.endpoints import (
    audit,
    auth,
    catalog_admin,
    catalog_public,
    cost_estimates,
    custom_requests,
    customers,
    files,
    health,
    materials,
    orders,
    payments,
    quotes,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(audit.router)
# Public storefront
api_router.include_router(catalog_public.router)
api_router.include_router(custom_requests.router)
api_router.include_router(files.router)
# Customer commerce (Phase 3): quotes / orders / payments
api_router.include_router(quotes.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
# Admin
api_router.include_router(catalog_admin.router)
api_router.include_router(materials.router)
api_router.include_router(customers.router)
api_router.include_router(custom_requests.admin_router)
api_router.include_router(files.admin_media_router)
api_router.include_router(cost_estimates.router)
api_router.include_router(quotes.admin_router)
api_router.include_router(orders.admin_router)
api_router.include_router(payments.admin_router)
