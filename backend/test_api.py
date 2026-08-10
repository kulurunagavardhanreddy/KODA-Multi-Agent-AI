import pytest
from fastapi.testclient import TestClient
from main import app
from backend.database.chat_database import init_db

# Guarantee database is fully initialized before tests run
init_db()

client = TestClient(app)

def test_health_check():
    """Verify the health check endpoint returns 200 OK and expected structure."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "message" in data

def test_get_config():
    """Verify the config endpoint exposes the Google Client ID."""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "google_client_id" in data

def test_guest_login():
    """Verify guest login returns a valid JWT token."""
    response = client.post("/api/guest-login")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["username"] == "Guest"
    assert data["message"] == "Guest login successful"

def test_email_intelligence_workflow():
    """Verify standard settings CRUD, digest metrics, and disconnect lifecycle checks."""
    import uuid
    # 1. Sign up a test user with a random email to prevent duplicate runs collision
    test_email = f"test_{uuid.uuid4().hex}@example.com"
    test_pwd = "TestPassword123!"
    
    signup_res = client.post("/api/signup", json={
        "email": test_email,
        "username": "TestUserInt",
        "password": test_pwd
    })
    assert signup_res.status_code == 200
    
    # 2. Login as the test user
    login_res = client.post("/api/login", json={
        "email": test_email,
        "password": test_pwd
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Fetch settings (should default to OFF)
    get_res = client.get("/api/email/settings", headers=headers)
    assert get_res.status_code == 200
    perms = get_res.json()
    assert perms["enabled"] == 0
    assert perms["can_read"] == 0
    
    # 4. Fetch dashboard when disabled (should return 403)
    dash_disabled_res = client.get("/api/email/dashboard", headers=headers)
    assert dash_disabled_res.status_code == 403
    
    # 5. Enable email intelligence settings
    payload = {
        "enabled": 1,
        "connected_email": test_email,
        "can_read": 1,
        "can_summarize": 1,
        "can_prioritize": 1,
        "can_notify": 1,
        "can_send": 0,
        "can_archive": 1,
        "can_delete": 0,
        "can_read_attachments": 0
    }
    save_res = client.post("/api/email/settings", json=payload, headers=headers)
    assert save_res.status_code == 200
    perms_saved = save_res.json()
    assert perms_saved["enabled"] == 1
    assert perms_saved["connected_email"] == test_email
    assert perms_saved["can_read"] == 1
    
    # 6. Expose sandbox mock emails
    mock_res = client.post("/api/email/dev-mock-generate", headers=headers)
    assert mock_res.status_code == 200
    
    # 7. Fetch digest dashboard
    dash_res = client.get("/api/email/dashboard", headers=headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "digest" in dash_data
    assert "metrics" in dash_data
    assert dash_data["metrics"]["total_unread"] == 5
    assert dash_data["metrics"]["estimated_time_saved_minutes"] > 0
    
    # 8. Disconnect service with data cleanup
    disc_res = client.post("/api/email/disconnect", json={"delete_data": True}, headers=headers)
    assert disc_res.status_code == 200
    
    # 9. Verify settings are reset and dashboard is disabled again
    get_after_res = client.get("/api/email/settings", headers=headers)
    assert get_after_res.status_code == 200
    perms_after = get_after_res.json()
    assert perms_after["enabled"] == 0
    assert perms_after["connected_email"] is None
    
    dash_after_res = client.get("/api/email/dashboard", headers=headers)
    assert dash_after_res.status_code == 403