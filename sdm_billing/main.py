import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

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

# Mount static assets
try:
    config.STATIC_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


# Optional single-user authentication
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    settings = config.load_settings()
    auth_enabled = settings.get("auth_enabled", False)

    # Allowed paths without auth
    path = request.url.path
    if not auth_enabled or path.startswith("/static") or path in ("/login", "/docs", "/openapi.json"):
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
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
