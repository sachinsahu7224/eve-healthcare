from fastapi.testclient import TestClient

from app.models.user import User


def test_signup_success(client: TestClient):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["role"] == "PATIENT"
    assert "password" not in data
    assert "password_hash" not in data


def test_signup_duplicate_email(client: TestClient, patient_user: User):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": patient_user.email,
            "password": "AnotherPassword123!",
            "full_name": "Duplicate User",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_login_success(client: TestClient, patient_user: User):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": patient_user.email,
            "password": "PatientPass123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == patient_user.email


def test_login_invalid_password(client: TestClient, patient_user: User):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": patient_user.email,
            "password": "WrongPassword999!",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_email(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "AnyPassword123!",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_protected_endpoint_without_jwt(client: TestClient):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Authentication token is missing" in response.json()["detail"]


def test_protected_endpoint_with_invalid_jwt(client: TestClient):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401
    assert "Invalid authentication token" in response.json()["detail"]


def test_get_me_success(client: TestClient, patient_headers: dict, patient_user: User):
    response = client.get("/api/v1/auth/me", headers=patient_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == patient_user.id
    assert data["email"] == patient_user.email
    assert data["role"] == patient_user.role
