"""auth_user_service/fastapi/main.py"""

import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from auth_user_service.routes import api_router
from auth_user_service.core.config import settings
from auth_sdk_m8.observability import metrics as _metrics
from auth_sdk_m8.observability.middleware import MetricsMiddleware

_metrics.setup(
    enabled=settings.METRICS_ENABLED,
    groups_str=settings.METRICS_GROUPS,
    api_prefix=settings.API_PREFIX,
)


def custom_generate_unique_id(route: APIRoute) -> str:
    """
    Generate a unique identifier for a given API route.

    Args:
        route (APIRoute):
            The API route for which to generate the unique identifier.

    Returns:
        str:
            A unique identifier string composed of the route's
            first tag and name.
    """
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    max_age=3600,  # cache preflight requests for 1 hour
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.TOKENS_ENCRYPTION_KEY.get_secret_value(),
    max_age=3600,
)

if settings.METRICS_ENABLED:
    app.add_middleware(MetricsMiddleware)

app.mount(
    f"{settings.API_PREFIX}/static",
    StaticFiles(directory=settings.STATIC_BASE_PATH),
    name="static",
)

app.include_router(api_router, prefix=settings.API_PREFIX)

if settings.METRICS_ENABLED:

    @app.get(f"{settings.API_PREFIX}/metrics", include_in_schema=False, tags=["observability"])
    def metrics_endpoint() -> Response:
        """Expose Prometheus metrics."""
        content, content_type = _metrics.render()
        return Response(content=content, media_type=content_type)


@app.exception_handler(StarletteHTTPException)
async def custom_error_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    """Redirect OAuth error pages; return JSON for all other HTTP exceptions."""
    from_path = request.url.path
    if any(x in from_path for x in ["login_success", "oauth-callback"]):
        redirect = RedirectResponse(url=request.url_for("google_auth_login"))
        request.session["error"] = str(exc)
        return redirect
    headers = dict(exc.headers) if exc.headers else {}
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


if __name__ == "__main__":
    uvicorn.run("auth_user_service.main:app", host="0.0.0.0", port=5378, reload=True)
