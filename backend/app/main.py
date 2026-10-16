import logging
import time
import uuid

from fastapi import APIRouter, FastAPI, Request

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.health import router as health_router
from app.core.logging import bind_log_context, clear_log_context, configure_logging
from app.core.rate_limit import register_rate_limit
from app.modules.admin.router import router as admin_router
from app.modules.assessments.router import router as assessments_router
from app.modules.auth.router import router as auth_router
from app.modules.contests.router import router as contests_router
from app.modules.essays.router import router as essays_router
from app.modules.invites.router import router as invites_router
from app.modules.planner.router import router as planner_router
from app.modules.questions.router import router as questions_router
from app.modules.stats.router import router as stats_router
from app.modules.system.router import router as system_router
from app.modules.users.router import router as users_router
from app.storage.router import router as files_router

logger = logging.getLogger("app.request")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Rumo1000 API", version="0.1.0")
    register_error_handlers(app)
    register_rate_limit(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        clear_log_context()
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        bind_log_context(request_id=request_id)
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path != "/health":
            logger.info(
                "request",
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                },
            )
        return response

    api = APIRouter(prefix="/api/v1")
    api.include_router(health_router)
    api.include_router(files_router)
    api.include_router(auth_router)
    api.include_router(invites_router)
    api.include_router(users_router)
    api.include_router(essays_router)
    api.include_router(questions_router)
    api.include_router(planner_router)
    api.include_router(admin_router)
    api.include_router(contests_router)
    api.include_router(assessments_router)
    api.include_router(stats_router)
    api.include_router(system_router)
    app.include_router(api)
    # Também na raiz, para healthcheck do container/proxy.
    app.include_router(health_router, include_in_schema=False)
    return app


app = create_app()
