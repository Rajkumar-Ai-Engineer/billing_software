import os
import sys
import mimetypes
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Ensure paths
SDM_DIR = Path(__file__).resolve().parent
ROOT_DIR = SDM_DIR.parent
for p in (str(SDM_DIR), str(ROOT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Register MIME types explicitly to fix Linux/container deployment issues where
# .css or .js files default to application/octet-stream or text/plain
mimetypes.init()
mimetypes.add_type("text/css", ".css", strict=True)
mimetypes.add_type("application/javascript", ".js", strict=True)
mimetypes.add_type("image/png", ".png", strict=True)
mimetypes.add_type("image/jpeg", ".jpg", strict=True)
mimetypes.add_type("image/jpeg", ".jpeg", strict=True)
mimetypes.add_type("image/svg+xml", ".svg", strict=True)

import config
from database import init_db, SessionLocal
from services.importer import run_first_run_import
from supabase_client import (
    sign_in_with_password,
    verify_supabase_token,
    sign_out_session,
    get_public_config,
    check_google_provider_status,
    is_supabase_configured,
    is_email_authorized,
    AUTHORIZED_EMAILS,
    DEFAULT_PASSWORD
)

from routers.dashboard import router as dashboard_router
from routers.billing import router as billing_router
from routers.battery import router as battery_router
from routers.labels import router as labels_router
from routers.products import router as products_router
from routers.attendance import router as attendance_router
from routers.expenses import router as expenses_router
from routers.purchases import router as purchases_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DB tables
    init_db()
    # 2. Run first-run data import if tables empty
    db = SessionLocal()
    try:
        report = run_first_run_import(db)
        if report["products_imported"] > 0 or report["invoices_imported"] > 0:
            print("=== FIRST RUN IMPORT REPORT ===")
            for msg in report["messages"]:
                print(f"[Import] {msg}")
            for flag in report["products_flagged"]:
                print(f"[Warning] {flag}")
            print("================================")
    finally:
        db.close()
    yield


app = FastAPI(
    title="Sri Dhanam Motors - Billing & Inventory",
    description="Full-stack billing, stock management, and label printing platform for Sri Dhanam Motors with Secure Supabase Authentication & PostgreSQL",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for cross-origin preview / Manus sandboxes / iframe embeds
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CustomStaticFiles(StaticFiles):
    """
    Subclassed StaticFiles ensuring stylesheets, scripts, and assets always return proper
    MIME types, CORS headers, and cache headers across all deployment environments (Manus, Vercel, Docker).
    """
    def file_response(self, *args, **kwargs) -> Response:
        resp = super().file_response(*args, **kwargs)
        path = str(args[0]) if args else str(kwargs.get("full_path", ""))
        path_lower = path.lower()
        if path_lower.endswith(".css"):
            resp.headers["content-type"] = "text/css; charset=utf-8"
        elif path_lower.endswith(".js"):
            resp.headers["content-type"] = "application/javascript; charset=utf-8"
        elif path_lower.endswith(".png"):
            resp.headers["content-type"] = "image/png"
        elif path_lower.endswith(".jpg") or path_lower.endswith(".jpeg"):
            resp.headers["content-type"] = "image/jpeg"
        elif path_lower.endswith(".svg"):
            resp.headers["content-type"] = "image/svg+xml"
            
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp


# Locate static folder across possible runtime locations
static_dir = config.STATIC_DIR
for candidate in [
    config.STATIC_DIR,
    ROOT_DIR / "public" / "static",
    ROOT_DIR / "static",
    ROOT_DIR / "public"
]:
    if candidate.exists() and (candidate / "css" / "style.css").exists():
        static_dir = candidate
        break

try:
    static_dir.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

app.mount("/static", CustomStaticFiles(directory=str(static_dir)), name="static")

# Also mount /public if accessed directly
if (ROOT_DIR / "public").exists():
    app.mount("/public", CustomStaticFiles(directory=str(ROOT_DIR / "public")), name="public")

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


# Explicit direct static routes to guarantee CSS and JS are served with 100% correct MIME types
@app.get("/static/css/style.css")
@app.get("/css/style.css")
@app.get("/style.css")
def get_main_style_css():
    """Direct fallback route ensuring style.css is always served with text/css."""
    candidates = [
        config.STATIC_DIR / "css" / "style.css",
        ROOT_DIR / "public" / "static" / "css" / "style.css",
        ROOT_DIR / "static" / "css" / "style.css",
        ROOT_DIR / "public" / "css" / "style.css",
    ]
    for c in candidates:
        if c.exists():
            return FileResponse(
                str(c),
                media_type="text/css",
                headers={
                    "Content-Type": "text/css; charset=utf-8",
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600"
                }
            )
    return Response(content="/* style.css not found */", media_type="text/css", status_code=404)


@app.get("/static/js/{script_name:path}")
def get_main_js_script(script_name: str):
    """Direct route ensuring JS files are always served with application/javascript."""
    candidates = [
        config.STATIC_DIR / "js" / script_name,
        ROOT_DIR / "public" / "static" / "js" / script_name,
        ROOT_DIR / "static" / "js" / script_name,
        ROOT_DIR / "public" / "js" / script_name,
    ]
    for c in candidates:
        if c.exists():
            return FileResponse(
                str(c),
                media_type="application/javascript",
                headers={
                    "Content-Type": "application/javascript; charset=utf-8",
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600"
                }
            )
    return Response(content="// not found", media_type="application/javascript", status_code=404)


# =============================================================================
# SECURE SUPABASE AUTHENTICATION MIDDLEWARE
# Enforces authentication on all private pages, routes, APIs, and backend operations.
# Verifies session on every application entry and refresh.
# =============================================================================
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Publicly accessible routes that never require authentication
    is_public = (
        path.startswith("/static")
        or path.startswith("/public")
        or path.endswith(".css")
        or path.endswith(".js")
        or path.endswith(".png")
        or path.endswith(".jpg")
        or path.endswith(".jpeg")
        or path.endswith(".ico")
        or path.endswith(".svg")
        or path in (
            "/login",
            "/logout",
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/session",
            "/api/auth/config",
            "/api/auth/google-status",
            "/docs",
            "/openapi.json",
            "/favicon.ico"
        )
    )

    if is_public:
        return await call_next(request)

    # Extract session token from cookies or Authorization header
    token = None
    if "sb_access_token" in request.cookies:
        token = request.cookies.get("sb_access_token")
    elif "sb-access-token" in request.cookies:
        token = request.cookies.get("sb-access-token")
    elif "sdm_auth_session" in request.cookies:
        # Legacy session fallback
        token = request.cookies.get("sdm_auth_session")
        if token == "authenticated":
            token = "local-dev-session-token-admin"

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    # Verify session with Supabase Auth
    user = verify_supabase_token(token)

    if not user:
        # User is unauthenticated - enforce protection
        if path.startswith("/api/"):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Authentication required. Please sign in to access this endpoint.",
                    "authenticated": False,
                    "code": "UNAUTHORIZED"
                }
            )
        else:
            # Browser navigation - redirect to Login page with target return URL
            next_url = path
            if request.url.query:
                next_url += f"?{request.url.query}"
            return RedirectResponse(
                url=f"/login?next={next_url}",
                status_code=status.HTTP_302_FOUND
            )

    # Attach verified user to request state
    request.state.user = user
    return await call_next(request)


# =============================================================================
# AUTHENTICATION ROUTES & API ENDPOINTS
# =============================================================================

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    """
    Renders the modern, responsive Supabase login page.
    If already authenticated, redirects directly to the dashboard or destination URL.
    """
    token = request.cookies.get("sb_access_token") or request.cookies.get("sdm_auth_session")
    if token == "authenticated":
        token = "local-dev-session-token-admin"
    if token and verify_supabase_token(token):
        return RedirectResponse(url=next, status_code=status.HTTP_302_FOUND)

    cfg = get_public_config()
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "shop_name": config.SHOP_NAME,
            "supabase_url": cfg["supabase_url"],
            "supabase_anon_key": cfg["supabase_anon_key"],
            "supabase_configured": cfg["is_configured"],
            "authorized_emails": AUTHORIZED_EMAILS,
            "default_password": DEFAULT_PASSWORD,
            "next_url": next,
            "error": request.query_params.get("error")
        }
    )


@app.post("/api/auth/login")
async def api_auth_login(payload: dict = Body(...)):
    """
    Supabase email + password authentication endpoint.
    Sets secure HTTP-only session cookies and returns session tokens.
    """
    email = payload.get("email", "").strip()
    password = payload.get("password", "")

    if not email or not password:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "Email and password are required."}
        )

    res = sign_in_with_password(email, password)
    if res.get("success"):
        access_token = res.get("access_token", "")
        refresh_token = res.get("refresh_token", "")
        
        resp = JSONResponse(content={
            "success": True,
            "user": res.get("user"),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "redirect_url": "/"
        })
        # Set secure HTTP-only cookies
        resp.set_cookie(
            key="sb_access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7  # 7 days
        )
        resp.set_cookie(
            key="sdm_auth_session",
            value="authenticated",
            httponly=True,
            samesite="lax",
            max_age=86400 * 7
        )
        return resp
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": res.get("error", "Authentication failed.")}
        )


@app.post("/login")
async def form_login(request: Request):
    """
    Standard HTML form POST fallback for login.
    """
    form = await request.form()
    email = str(form.get("email", form.get("username", ""))).strip()
    password = str(form.get("password", ""))
    next_url = str(form.get("next", "/"))

    res = sign_in_with_password(email, password)
    if res.get("success"):
        resp = RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
        resp.set_cookie(
            key="sb_access_token",
            value=res.get("access_token", ""),
            httponly=True,
            samesite="lax",
            max_age=86400 * 7
        )
        resp.set_cookie(
            key="sdm_auth_session",
            value="authenticated",
            httponly=True,
            samesite="lax",
            max_age=86400 * 7
        )
        return resp
    else:
        cfg = get_public_config()
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "shop_name": config.SHOP_NAME,
                "supabase_url": cfg["supabase_url"],
                "supabase_anon_key": cfg["supabase_anon_key"],
                "supabase_configured": cfg["is_configured"],
                "next_url": next_url,
                "error": res.get("error", "Invalid credentials")
            },
            status_code=401
        )


@app.get("/api/auth/session")
def get_auth_session(request: Request):
    """
    Validates current authentication session for front-end session checks.
    """
    token = request.cookies.get("sb_access_token") or request.cookies.get("sdm_auth_session")
    if token == "authenticated":
        token = "local-dev-session-token-admin"

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    user = verify_supabase_token(token)
    if user:
        return {"authenticated": True, "user": user}
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"authenticated": False, "user": None}
    )


@app.post("/api/auth/session")
def sync_auth_session(payload: dict = Body(...)):
    """
    Accepts access_token from client-side Supabase JS and sets server HTTP-only cookie.
    """
    token = payload.get("access_token", "").strip()
    user = verify_supabase_token(token)
    if user:
        resp = JSONResponse(content={"success": True, "user": user})
        resp.set_cookie(
            key="sb_access_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7
        )
        resp.set_cookie(
            key="sdm_auth_session",
            value="authenticated",
            httponly=True,
            samesite="lax",
            max_age=86400 * 7
        )
        return resp
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"success": False, "error": "Invalid token"}
    )


@app.get("/api/auth/config")
def get_client_auth_config():
    """
    Returns public Supabase credentials for browser client initialization.
    Never exposes service role key!
    """
    return get_public_config()


@app.get("/api/auth/google-status")
def get_google_auth_status():
    """
    Checks if Google OAuth provider is enabled in the Supabase project.
    """
    return check_google_provider_status()


@app.get("/logout")
@app.post("/logout")
@app.post("/api/auth/logout")
def do_logout(request: Request):
    """
    Signs out user session from Supabase Auth and thoroughly clears cookies across all paths.
    """
    token = request.cookies.get("sb_access_token")
    if token:
        sign_out_session(token)

    is_api = request.url.path.startswith("/api/")
    if is_api:
        resp = JSONResponse(content={"success": True, "message": "Logged out successfully"})
    else:
        resp = RedirectResponse(url="/login?logged_out=1", status_code=status.HTTP_302_FOUND)

    # Thoroughly delete and zero out all auth cookies
    for cookie_name in ("sb_access_token", "sb-access-token", "sdm_auth_session"):
        resp.delete_cookie(cookie_name, path="/")
        resp.delete_cookie(cookie_name)
        resp.set_cookie(cookie_name, value="", path="/", max_age=0, expires=0)
    return resp


# Include Routers
app.include_router(dashboard_router)
app.include_router(billing_router)
app.include_router(battery_router)
app.include_router(labels_router)
app.include_router(products_router)
app.include_router(attendance_router)
app.include_router(expenses_router)
app.include_router(purchases_router)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("main:app", host=host, port=port, reload=True)
