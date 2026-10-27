import os
import sys
import mimetypes
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
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
    description="Full-stack billing, stock management, and label printing platform for Sri Dhanam Motors",
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


# Optional single-user authentication
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    settings = config.load_settings()
    auth_enabled = settings.get("auth_enabled", False)

    # Allowed paths without auth - ensure static assets, css, js, and images are NEVER blocked
    path = request.url.path
    if (
        not auth_enabled
        or path.startswith("/static")
        or path.startswith("/public")
        or path.endswith(".css")
        or path.endswith(".js")
        or path.endswith(".png")
        or path.endswith(".jpg")
        or path.endswith(".jpeg")
        or path.endswith(".ico")
        or path in ("/login", "/docs", "/openapi.json", "/favicon.ico")
    ):
        return await call_next(request)

    # Check session cookie
    auth_cookie = request.cookies.get("sdm_auth_session")
    if auth_cookie != "authenticated":
        return RedirectResponse(url="/login")

    return await call_next(request)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"shop_name": config.SHOP_NAME})


@app.post("/login")
async def do_login(request: Request):
    form = await request.form()
    password = form.get("password")
    settings = config.load_settings()
    expected_pwd = settings.get("auth_password", config.AUTH_PASSWORD)

    if password == expected_pwd:
        resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        resp.set_cookie(key="sdm_auth_session", value="authenticated", httponly=True)
        return resp
    else:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"shop_name": config.SHOP_NAME, "error": "Invalid Password"},
            status_code=400
        )


@app.get("/logout")
def do_logout():
    resp = RedirectResponse(url="/login")
    resp.delete_cookie("sdm_auth_session")
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
