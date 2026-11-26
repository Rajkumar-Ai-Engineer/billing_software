import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="module")
def unauthed_client():
    with TestClient(app) as c:
        c.cookies.clear()
        yield c


@pytest.fixture(scope="module")
def authed_client():
    with TestClient(app) as c:
        c.cookies.set("sb_access_token", "local-dev-session-token-admin")
        yield c


def test_unauthenticated_page_access_redirects_to_login(unauthed_client):
    """
    Scenario 1 & 5: Open the application without logging in or access protected URL -> Redirects to Login page
    """
    unauthed_client.cookies.clear()
    # Root dashboard
    r = unauthed_client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]
    assert "next=%2F" in r.headers["location"] or "next=/" in r.headers["location"]

    # Protected page: spare bill
    r = unauthed_client.get("/spare-bill", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]

    # Protected page: products
    r = unauthed_client.get("/products", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]

    # Protected page: expenses
    r = unauthed_client.get("/expenses", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


def test_unauthenticated_api_access_rejected_with_401(unauthed_client):
    """
    Scenario 7: Access protected APIs without authentication -> Reject request with 401 Unauthorized
    """
    unauthed_client.cookies.clear()
    # Protected API: dashboard
    r = unauthed_client.get("/api/dashboard")
    assert r.status_code == 401
    data = r.json()
    assert data["authenticated"] is False
    assert data["code"] == "UNAUTHORIZED"

    # Protected API: products search
    r = unauthed_client.get("/api/products/search")
    assert r.status_code == 401

    # Protected API: session check
    r = unauthed_client.get("/api/auth/session")
    assert r.status_code == 401
    assert r.json()["authenticated"] is False


def test_public_routes_accessible_without_auth(unauthed_client):
    """
    Public static assets and login page must remain accessible without auth
    """
    unauthed_client.cookies.clear()
    r = unauthed_client.get("/login")
    assert r.status_code == 200
    assert "DHANAM MOTORS" in r.text.upper()
    assert "Sign In" in r.text

    r = unauthed_client.get("/api/auth/config")
    assert r.status_code == 200
    cfg = r.json()
    assert "supabase_url" in cfg
    assert "supabase_anon_key" in cfg


def test_login_with_invalid_credentials_fails(unauthed_client):
    """
    Scenario 2: Enter incorrect credentials -> Show an error
    """
    unauthed_client.cookies.clear()
    r = unauthed_client.post("/api/auth/login", json={
        "email": "wrong_staff@sridhanammotors.com",
        "password": "wrong_password_xyz"
    })
    assert r.status_code == 401
    data = r.json()
    assert data["success"] is False
    assert "error" in data


def test_login_with_valid_credentials_succeeds(unauthed_client):
    """
    Scenario 3: Enter valid credentials -> Authenticates and sets session
    Tests the 3 authorized administrator emails
    """
    for email in ["sdmortrs@gmail.com", "muthukumaransuthagar48@gmail.com", "tech84602@gmail.com"]:
        unauthed_client.cookies.clear()
        r = unauthed_client.post("/api/auth/login", json={
            "email": email,
            "password": "dhanam@#123"
        })
        assert r.status_code == 200, f"Login failed for authorized email {email}: {r.text}"
        data = r.json()
        assert data["success"] is True
        assert "access_token" in data
        assert data["user"]["email"] == email
        assert "sb_access_token" in r.cookies


def test_unauthorized_email_rejected(unauthed_client):
    """
    Scenario: Verify that only the 3 authorized emails are permitted to sign in
    """
    unauthed_client.cookies.clear()
    r = unauthed_client.post("/api/auth/login", json={
        "email": "unauthorized_user@example.com",
        "password": "dhanam@#123"
    })
    assert r.status_code == 401
    data = r.json()
    assert data["success"] is False
    assert "Access Denied" in data["error"] or "not authorized" in data["error"]


def test_authorized_email_wrong_password_rejected(unauthed_client):
    """
    Scenario: Verify that an authorized email with wrong password is rejected
    """
    unauthed_client.cookies.clear()
    r = unauthed_client.post("/api/auth/login", json={
        "email": "tech84602@gmail.com",
        "password": "wrong_password_123"
    })
    assert r.status_code == 401
    data = r.json()
    assert data["success"] is False
    assert "Invalid email or password" in data["error"] or "credentials" in data["error"]


def test_authenticated_access_and_refresh_session(authed_client):
    """
    Scenario 4: Refresh the dashboard -> Verify session and maintain access
    """
    # Dashboard loads with 200 OK
    r = authed_client.get("/")
    assert r.status_code == 200
    assert "DHANAM MOTORS" in r.text.upper()

    # Session verification returns authenticated
    r = authed_client.get("/api/auth/session")
    assert r.status_code == 200
    data = r.json()
    assert data["authenticated"] is True
    assert data["user"]["role"] == "authenticated"

    # Protected API succeeds
    r = authed_client.get("/api/dashboard")
    assert r.status_code == 200


def test_logout_clears_session_and_redirects(authed_client):
    """
    Scenario 6: Logout -> Return to login and revoke session
    """
    r = authed_client.get("/logout", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]

    # API logout
    r = authed_client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json()["success"] is True
